#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from gh_cli import GhCliError
from gh_context import resolve_context
from paths import SETUP_HINT
from workflow_config import ConfigError, load_config
from work_queue_model import (
    WorkQueueError,
    fetch_issue,
    fetch_parent_issue,
    filter_issues,
    is_in_progress,
    list_open_task_issues,
    render_issue_rows,
    render_pr_body,
)


def _issue_payload(issue) -> dict[str, object]:
    payload: dict[str, object] = {
        "issue_number": issue.issue_number,
        "issue_id": issue.issue_id,
        "title": issue.title,
        "url": issue.url,
        "state": issue.state,
        "issue_type": issue.issue_type,
        "blocked_by": [
            {
                "number": blocker.number,
                "state": blocker.state,
                "url": blocker.url,
            }
            for blocker in issue.blocked_by
        ],
        "closing_prs": [
            {"number": pr.number, "state": pr.state, "url": pr.url} for pr in issue.closing_prs
        ],
        "body": issue.body,
        "parent_issue": None,
    }
    if issue.parent_issue is not None:
        payload["parent_issue"] = {
            "number": issue.parent_issue.number,
            "title": issue.parent_issue.title,
            "url": issue.parent_issue.url,
            "body": issue.parent_issue.body,
        }
    return payload


def _cmd_list(args: argparse.Namespace) -> int:
    issues = list_open_task_issues(
        owner=args.repo_owner,
        name=args.repo_name,
        limit=args.limit,
        work_issue_type=getattr(args, "work_issue_type", "Task"),
    )
    issues = filter_issues(issues=issues, ready=args.ready)
    if args.format == "json":
        print(json.dumps([_issue_payload(issue) for issue in issues], indent=2))
        return 0
    print(render_issue_rows(issues))
    return 0


def _cmd_next(args: argparse.Namespace) -> int:
    issues = list_open_task_issues(
        owner=args.repo_owner,
        name=args.repo_name,
        limit=args.limit,
        work_issue_type=getattr(args, "work_issue_type", "Task"),
    )
    issues = filter_issues(issues=issues, ready=args.ready)
    issues = [issue for issue in issues if not is_in_progress(issue)]
    if not issues:
        print("No matching issues found.")
        return 1
    issue = issues[0]
    if args.format == "json":
        issue = replace(
            issue,
            parent_issue=fetch_parent_issue(
                owner=args.repo_owner,
                name=args.repo_name,
                number=issue.issue_number,
            ),
        )
        print(json.dumps(_issue_payload(issue), indent=2))
        return 0
    blocked_by = " ".join(f"#{b.number}" for b in issue.blocked_by) or "(none)"
    print(f"#{issue.issue_number} {issue.title}")
    print(f"url: {issue.url}")
    print(f"blocked_by: {blocked_by}")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    issue = fetch_issue(owner=args.repo_owner, name=args.repo_name, number=args.issue)
    expected_type = getattr(args, "expected_issue_type", "Task")
    if issue.issue_type != expected_type:
        raise WorkQueueError(f"Issue #{issue.issue_number} is not a {expected_type} issue")
    if args.format == "json":
        issue = replace(
            issue,
            parent_issue=fetch_parent_issue(
                owner=args.repo_owner,
                name=args.repo_name,
                number=issue.issue_number,
            ),
        )
        print(json.dumps(_issue_payload(issue), indent=2))
        return 0
    blocked_by = " ".join(f"#{b.number}" for b in issue.blocked_by) or "(none)"
    print(f"#{issue.issue_number} {issue.title}")
    print(f"url: {issue.url}")
    print(f"state: {issue.state}")
    print(f"blocked_by: {blocked_by}")
    return 0


def _cmd_pr_body(args: argparse.Namespace) -> int:
    issue = fetch_issue(owner=args.repo_owner, name=args.repo_name, number=args.issue)
    body = render_pr_body(
        template_path=args.pr_template,
        issue=issue,
        specs_changed=args.specs_changed,
        tests_run=args.tests_run,
        close_keyword=getattr(args, "close_keyword", "Fixes"),
    )
    if not body:
        print("ERROR: PR template not found or empty.", file=sys.stderr)
        return 1
    print(body)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Operate a GitHub issues-only Task work queue. {SETUP_HINT}"
    )

    def add_common_args(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--repo",
            default=None,
            help="Target repository (OWNER/REPO). Defaults to current repo via gh.",
        )
        target.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of work issues to fetch (best-effort).",
        )
        target.add_argument("--config", type=Path, default=None)

    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List open Task issues.")
    add_common_args(p_list)
    p_list.add_argument("--ready", action="store_true", help="Only include ready issues.")
    p_list.add_argument("--format", choices=("table", "json"), default="table")
    p_list.set_defaults(handler=_cmd_list)

    p_next = sub.add_parser("next", help="Show next Task issue (skips in-progress).")
    add_common_args(p_next)
    p_next.add_argument("--ready", action="store_true", help="Require blockers closed.")
    p_next.add_argument("--format", choices=("table", "json"), default="table")
    p_next.set_defaults(handler=_cmd_next)

    p_show = sub.add_parser("show", help="Show one Task issue payload.")
    add_common_args(p_show)
    p_show.add_argument("--issue", type=int, required=True, help="Issue number.")
    p_show.add_argument("--format", choices=("table", "json"), default="table")
    p_show.set_defaults(handler=_cmd_show)

    p_pr = sub.add_parser("pr-body", help="Render paste-ready PR body from template.")
    add_common_args(p_pr)
    p_pr.add_argument("--issue", type=int, required=True, help="Issue number.")
    p_pr.add_argument(
        "--pr-template",
        type=Path,
        default=None,
        help="PR template path.",
    )
    p_pr.add_argument("--specs-changed", default="", help="Value for {{SPECS_CHANGED}}.")
    p_pr.add_argument("--tests-run", default="", help="Value for {{TESTS_RUN}}.")
    p_pr.set_defaults(handler=_cmd_pr_body)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        config = load_config(Path.cwd(), config_path=args.config)
        pr_policy = config.data["pr_policy"]
        if pr_policy.get("allow_admin") or pr_policy.get("merge") != "opt-in":
            raise WorkQueueError("pr_policy must forbid admin bypass and keep merge opt-in")
        context = resolve_context(
            repo=args.repo,
            repo_root=config.repo_root,
            context_path=config.output_path("cache") / "context.json",
        )
        args.work_issue_type = config.work_issue_type
        args.expected_issue_type = config.work_issue_type
        args.close_keyword = pr_policy["close_keyword"]
        if getattr(args, "pr_template", None) is None:
            args.pr_template = config.template_path("pr")
    except (GhCliError, ConfigError, WorkQueueError) as exc:
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
    except WorkQueueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
