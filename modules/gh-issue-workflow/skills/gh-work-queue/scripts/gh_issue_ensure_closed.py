#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from gh_cli import GhCliError  # noqa: E402
from gh_context import resolve_context  # noqa: E402
from gh_graphql import run_graphql  # noqa: E402
from paths import SETUP_HINT  # noqa: E402
from validation import optional_int, optional_str, require_dict, require_str  # noqa: E402


class EnsureClosedError(RuntimeError):
    pass


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    try:
        return require_dict(value, label)
    except ValueError as exc:
        raise EnsureClosedError(str(exc)) from exc


def _require_str(value: Any, label: str) -> str:
    try:
        return require_str(value, label)
    except ValueError as exc:
        raise EnsureClosedError(str(exc)) from exc


_ISSUE_STATE_QUERY = """
query FetchIssueState($owner: String!, $repo: String!, $issue: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $issue) {
      number
      title
      url
      state
      closedAt
      closedByPullRequestsReferences(first: 20) {
        nodes { number state url }
      }
    }
  }
}
""".strip()


def fetch_issue_state(*, owner: str, repo: str, issue_number: int) -> dict[str, Any]:
    data = run_graphql(
        query=_ISSUE_STATE_QUERY,
        variables={"owner": owner, "repo": repo, "issue": issue_number},
    )
    repository = _require_dict(data.get("repository"), "repository")
    issue_raw = repository.get("issue")
    if issue_raw is None:
        raise EnsureClosedError(f"Issue not found: #{issue_number}")
    issue = _require_dict(issue_raw, "issue")

    state = str(issue.get("state") or "").upper()
    closing_prs: list[dict[str, Any]] = []
    closing_conn = issue.get("closedByPullRequestsReferences")
    if isinstance(closing_conn, dict):
        nodes = closing_conn.get("nodes")
        if isinstance(nodes, list):
            for raw in nodes:
                if not isinstance(raw, dict):
                    continue
                pr_state = str(raw.get("state") or "").upper()
                pr_number = optional_int(raw.get("number"))
                closing_prs.append({
                    "number": pr_number,
                    "state": pr_state,
                    "url": optional_str(raw.get("url")),
                })
    closing_prs.sort(key=lambda pr: pr.get("number") or 0)

    return {
        "issue": {
            "number": issue_number,
            "title": str(issue.get("title") or ""),
            "url": _require_str(issue.get("url"), "issue.url"),
            "state": state,
            "closed_at": optional_str(issue.get("closedAt")),
        },
        "closing_prs": closing_prs,
    }


def _diagnostic_suggestions(
    *, issue_number: int, closing_prs: list[dict[str, Any]]
) -> list[str]:
    pr_numbers = [
        pr.get("number") for pr in closing_prs if isinstance(pr.get("number"), int)
    ]
    pr_hint = (
        f" (closing PRs: {', '.join(f'#{n}' for n in pr_numbers)})"
        if pr_numbers
        else ""
    )
    return [
        (
            "Confirm the merged PR targets the default branch and includes "
            f"`Fixes #{issue_number}`.{pr_hint}"
        ),
        (
            "If the PR doesn't (or can't) auto-close the issue, close the issue "
            "manually and reference the merged PR."
        ),
    ]


def _cmd_ensure_closed(args: argparse.Namespace) -> int:
    deadline = time.monotonic() + args.timeout_seconds
    while True:
        payload = fetch_issue_state(
            owner=args.repo_owner,
            repo=args.repo_name,
            issue_number=args.issue,
        )
        issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
        state = str(issue.get("state") or "").upper()
        if state == "CLOSED":
            if args.format == "json":
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                url = issue.get("url") or ""
                print(f"Issue #{args.issue} is CLOSED. {url}".strip())
            return 0

        now = time.monotonic()
        if now >= deadline:
            closing_prs = payload.get("closing_prs")
            closing_list = closing_prs if isinstance(closing_prs, list) else []
            suggestions = _diagnostic_suggestions(
                issue_number=args.issue,
                closing_prs=[row for row in closing_list if isinstance(row, dict)],
            )
            if args.format == "json":
                out = dict(payload)
                out["error"] = f"Timed out waiting for issue #{args.issue} to close."
                out["suggestions"] = suggestions
                print(json.dumps(out, indent=2, sort_keys=True))
            else:
                url = issue.get("url") or ""
                message = (
                    f"ERROR: Timed out waiting for issue #{args.issue} to close. {url}"
                ).strip()
                print(message)
                for suggestion in suggestions:
                    print(f"- {suggestion}")
            return 2

        time.sleep(max(1, int(args.interval_seconds)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Verify (and optionally poll) that a GitHub issue is CLOSED. {SETUP_HINT}"
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Target repository (OWNER/REPO). Defaults to current repo via gh.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_ensure = sub.add_parser(
        "ensure-closed", help="Poll until issue is CLOSED or timeout."
    )
    p_ensure.add_argument("--issue", type=int, required=True, help="Issue number.")
    p_ensure.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Max time to wait before failing.",
    )
    p_ensure.add_argument(
        "--interval-seconds",
        type=int,
        default=5,
        help="Polling interval (seconds).",
    )
    p_ensure.add_argument("--format", choices=("text", "json"), default="text")
    p_ensure.set_defaults(handler=_cmd_ensure_closed)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        context = resolve_context(repo=args.repo)
    except GhCliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(SETUP_HINT, file=sys.stderr)
        return 1
    args.repo = context.repo
    args.repo_owner = context.repo_owner
    args.repo_name = context.repo_name
    try:
        return args.handler(args)
    except GhCliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(SETUP_HINT, file=sys.stderr)
        return 1
    except EnsureClosedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
