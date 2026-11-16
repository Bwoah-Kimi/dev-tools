#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from gh_cli import GhCliError  # noqa: E402
from gh_context import resolve_context  # noqa: E402
from gh_graphql import run_graphql  # noqa: E402
from paths import SETUP_HINT  # noqa: E402
from validation import optional_int, optional_str, require_dict, require_str  # noqa: E402


class PrThreadsError(RuntimeError):
    pass


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    try:
        return require_dict(value, label)
    except ValueError as exc:
        raise PrThreadsError(str(exc)) from exc


def _require_str(value: Any, label: str) -> str:
    try:
        return require_str(value, label)
    except ValueError as exc:
        raise PrThreadsError(str(exc)) from exc


_UNRESOLVED_THREADS_QUERY = """
query FetchUnresolvedThreads(
  $owner: String!
  $repo: String!
  $pr: Int!
  $cursor: String
) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      title
      url
      reviewThreads(first: 100, after: $cursor) {
        totalCount
        edges {
          node {
            id
            isResolved
            isOutdated
            isCollapsed
            path
            line
            startLine
            diffSide
            comments(first: 100) {
              totalCount
              nodes {
                id
                author { login }
                body
                createdAt
                updatedAt
                url
                outdated
              }
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
""".strip()


_RESOLVE_THREAD_MUTATION = """
mutation ResolveReviewThread($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread {
      id
      isResolved
      path
      line
    }
  }
}
""".strip()


def _normalize_thread(node: dict[str, Any]) -> dict[str, Any]:
    comments_conn = node.get("comments")
    comments_nodes: list[dict[str, Any]] = []
    if isinstance(comments_conn, dict):
        raw_nodes = comments_conn.get("nodes")
        if isinstance(raw_nodes, list):
            for raw in raw_nodes:
                if not isinstance(raw, dict):
                    continue
                author = raw.get("author")
                author_login = None
                if isinstance(author, dict):
                    author_login = optional_str(author.get("login"))
                comments_nodes.append({
                    "id": optional_str(raw.get("id")),
                    "author": author_login,
                    "body": str(raw.get("body") or ""),
                    "created_at": optional_str(raw.get("createdAt")),
                    "updated_at": optional_str(raw.get("updatedAt")),
                    "url": optional_str(raw.get("url")),
                    "outdated": bool(raw.get("outdated"))
                    if raw.get("outdated") is not None
                    else None,
                })
    return {
        "id": optional_str(node.get("id")),
        "path": optional_str(node.get("path")),
        "line": optional_int(node.get("line")),
        "start_line": optional_int(node.get("startLine")),
        "diff_side": optional_str(node.get("diffSide")),
        "is_resolved": bool(node.get("isResolved"))
        if node.get("isResolved") is not None
        else None,
        "is_outdated": bool(node.get("isOutdated"))
        if node.get("isOutdated") is not None
        else None,
        "is_collapsed": bool(node.get("isCollapsed"))
        if node.get("isCollapsed") is not None
        else None,
        "comments": comments_nodes,
    }


def fetch_unresolved_threads(
    *, owner: str, repo: str, pr_number: int
) -> dict[str, Any]:
    cursor: str | None = None
    pr_title = ""
    pr_url = ""
    threads: list[dict[str, Any]] = []

    while True:
        data = run_graphql(
            query=_UNRESOLVED_THREADS_QUERY,
            variables={"owner": owner, "repo": repo, "pr": pr_number, "cursor": cursor},
        )
        repository = _require_dict(data.get("repository"), "repository")
        pull_request = repository.get("pullRequest")
        if pull_request is None:
            raise PrThreadsError(f"PR not found: #{pr_number}")
        pr = _require_dict(pull_request, "pullRequest")
        pr_title = str(pr.get("title") or "")
        pr_url = str(pr.get("url") or "")

        threads_conn = _require_dict(
            pr.get("reviewThreads"), "pullRequest.reviewThreads"
        )
        edges = threads_conn.get("edges")
        if isinstance(edges, list):
            for edge in edges:
                if not isinstance(edge, dict):
                    continue
                node = edge.get("node")
                if not isinstance(node, dict):
                    continue
                is_resolved = node.get("isResolved")
                is_outdated = node.get("isOutdated")
                if is_resolved is False and is_outdated is False:
                    threads.append(_normalize_thread(node))

        page_info = threads_conn.get("pageInfo")
        if not isinstance(page_info, dict):
            break
        if not page_info.get("hasNextPage"):
            break
        end_cursor = page_info.get("endCursor")
        if not isinstance(end_cursor, str) or not end_cursor.strip():
            break
        cursor = end_cursor.strip()

    threads.sort(key=lambda thread: (thread.get("path") or "", thread.get("line") or 0))
    return {
        "pull_request": {"number": pr_number, "title": pr_title, "url": pr_url},
        "threads": threads,
        "unresolved_count": len(threads),
    }


def _cmd_unresolved(args: argparse.Namespace) -> int:
    payload = fetch_unresolved_threads(
        owner=args.repo_owner,
        repo=args.repo_name,
        pr_number=args.pr,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_resolve_thread(args: argparse.Namespace) -> int:
    data = run_graphql(
        query=_RESOLVE_THREAD_MUTATION,
        variables={"threadId": args.thread_id},
    )
    mutation = _require_dict(data.get("resolveReviewThread"), "resolveReviewThread")
    thread_raw = mutation.get("thread")
    if thread_raw is None:
        raise PrThreadsError("Mutation did not return thread payload.")
    thread = _require_dict(thread_raw, "resolveReviewThread.thread")
    thread_id = _require_str(thread.get("id"), "thread.id")
    is_resolved = thread.get("isResolved")
    if is_resolved is not True:
        raise PrThreadsError(f"Thread did not resolve: {thread_id}")
    out = {
        "id": thread_id,
        "is_resolved": True,
        "path": optional_str(thread.get("path")),
        "line": optional_int(thread.get("line")),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Fetch unresolved PR review threads and resolve threads by ID. {SETUP_HINT}"
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Target repository (OWNER/REPO). Defaults to current repo via gh.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_unresolved = sub.add_parser(
        "unresolved",
        help="Fetch unresolved, non-outdated review threads for a PR.",
    )
    p_unresolved.add_argument("--pr", type=int, required=True, help="PR number.")
    p_unresolved.set_defaults(handler=_cmd_unresolved)

    p_resolve = sub.add_parser(
        "resolve-thread", help="Resolve one review thread by ID."
    )
    p_resolve.add_argument(
        "--thread-id", required=True, help="Review thread GraphQL ID."
    )
    p_resolve.set_defaults(handler=_cmd_resolve_thread)

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
    except PrThreadsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
