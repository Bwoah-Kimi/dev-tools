#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gh_cli import GhCliError, run
from gh_graphql import run_graphql
from validation import require_int, require_str


class WorkQueueError(RuntimeError):
    pass


@dataclass(frozen=True)
class BlockedByRef:
    number: int
    state: str
    url: str


@dataclass(frozen=True)
class ClosingPrRef:
    number: int
    state: str
    url: str


@dataclass(frozen=True)
class ParentIssue:
    number: int
    title: str
    url: str
    body: str


@dataclass(frozen=True)
class QueueIssue:
    issue_id: str
    issue_number: int
    title: str
    url: str
    body: str
    state: str
    issue_type: str
    blocked_by: list[BlockedByRef]
    closing_prs: list[ClosingPrRef]
    parent_issue: ParentIssue | None = None


def _require_int(value: Any, label: str) -> int:
    try:
        return require_int(value, label)
    except ValueError as exc:
        raise WorkQueueError(str(exc)) from exc


def _require_str(value: Any, label: str) -> str:
    try:
        return require_str(value, label)
    except ValueError as exc:
        raise WorkQueueError(str(exc)) from exc


def _parse_blocked_by(nodes: Any) -> list[BlockedByRef]:
    if not isinstance(nodes, list):
        return []
    result: list[BlockedByRef] = []
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        try:
            number = _require_int(raw.get("number"), "blockedBy.number")
            state = str(raw.get("state") or "").upper()
            url = _require_str(raw.get("url"), "blockedBy.url")
        except WorkQueueError:
            continue
        result.append(BlockedByRef(number=number, state=state, url=url))
    return sorted(result, key=lambda row: row.number)


def _parse_closing_prs(nodes: Any) -> list[ClosingPrRef]:
    if not isinstance(nodes, list):
        return []
    result: list[ClosingPrRef] = []
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        try:
            number = _require_int(raw.get("number"), "closingPR.number")
            state = str(raw.get("state") or "").upper()
            url = _require_str(raw.get("url"), "closingPR.url")
        except WorkQueueError:
            continue
        result.append(ClosingPrRef(number=number, state=state, url=url))
    return sorted(result, key=lambda row: row.number)


def _parse_issue(node: dict[str, Any]) -> QueueIssue:
    issue_id = _require_str(node.get("id"), "issue.id")
    number = _require_int(node.get("number"), "issue.number")
    title = str(node.get("title") or f"#{number}")
    url = _require_str(node.get("url"), "issue.url")
    body = str(node.get("body") or "")
    state = str(node.get("state") or "").upper()
    issue_type = ""
    raw_issue_type = node.get("issueType")
    if isinstance(raw_issue_type, dict) and isinstance(raw_issue_type.get("name"), str):
        issue_type = raw_issue_type["name"].strip()
    blocked_by = _parse_blocked_by(
        node.get("blockedBy", {}).get("nodes") if isinstance(node.get("blockedBy"), dict) else None
    )
    closing_prs = _parse_closing_prs(
        node.get("closedByPullRequestsReferences", {}).get("nodes")
        if isinstance(node.get("closedByPullRequestsReferences"), dict)
        else None
    )
    return QueueIssue(
        issue_id=issue_id,
        issue_number=number,
        title=title,
        url=url,
        body=body,
        state=state,
        issue_type=issue_type,
        blocked_by=blocked_by,
        closing_prs=closing_prs,
    )


def fetch_parent_issue(*, owner: str, name: str, number: int) -> ParentIssue | None:
    try:
        payload = run(
            ["gh", "api", f"repos/{owner}/{name}/issues/{number}/parent"],
            expect_json=True,
        )
    except GhCliError as exc:
        message = str(exc)
        if "No parent issue found" in message or "(404)" in message:
            return None
        raise WorkQueueError(f"Unable to fetch parent issue for #{number}: {message}") from exc
    if not isinstance(payload, dict):
        raise WorkQueueError(f"Unexpected parent issue payload for #{number}: {payload!r}")
    parent_number = _require_int(payload.get("number"), "parent.number")
    parent_title = str(payload.get("title") or f"#{parent_number}")
    raw_url = payload.get("html_url")
    if not isinstance(raw_url, str) or not raw_url.strip():
        raw_url = payload.get("url")
    parent_url = _require_str(raw_url, "parent.url")
    return ParentIssue(
        number=parent_number,
        title=parent_title,
        url=parent_url,
        body=str(payload.get("body") or ""),
    )


_LIST_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(
      first: 100,
      after: $cursor,
      states: OPEN,
      orderBy: { field: CREATED_AT, direction: ASC }
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        id
        number
        title
        url
        body
        state
        issueType { name }
        blockedBy(first: 100) { nodes { number state url } }
        closedByPullRequestsReferences(first: 20) { nodes { number state url } }
      }
    }
  }
}
""".strip()


def list_open_task_issues(
    *,
    owner: str,
    name: str,
    limit: int | None = None,
) -> list[QueueIssue]:
    issues: list[QueueIssue] = []
    cursor: str | None = None
    while True:
        data = run_graphql(
            query=_LIST_QUERY,
            variables={"owner": owner, "name": name, "cursor": cursor},
        )
        repo = data.get("repository")
        if not isinstance(repo, dict):
            raise WorkQueueError(f"Repository not found: {owner}/{name}")
        conn = repo.get("issues")
        if not isinstance(conn, dict):
            break
        nodes = conn.get("nodes")
        if not isinstance(nodes, list):
            nodes = []
        for raw in nodes:
            if not isinstance(raw, dict):
                continue
            issue = _parse_issue(raw)
            if issue.issue_type != "Task":
                continue
            issues.append(issue)
            if limit is not None and len(issues) >= limit:
                return sorted(issues, key=lambda row: row.issue_number)
        page = conn.get("pageInfo")
        if not isinstance(page, dict):
            break
        if not page.get("hasNextPage"):
            break
        end_cursor = page.get("endCursor")
        cursor = end_cursor if isinstance(end_cursor, str) and end_cursor else None
        if cursor is None:
            break
    return sorted(issues, key=lambda row: row.issue_number)


_SHOW_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      id
      number
      title
      url
      body
      state
      issueType { name }
      blockedBy(first: 100) { nodes { number state url } }
      closedByPullRequestsReferences(first: 20) { nodes { number state url } }
    }
  }
}
""".strip()


def fetch_issue(*, owner: str, name: str, number: int) -> QueueIssue:
    data = run_graphql(
        query=_SHOW_QUERY,
        variables={"owner": owner, "name": name, "number": number},
    )
    repo = data.get("repository")
    if not isinstance(repo, dict):
        raise WorkQueueError(f"Repository not found: {owner}/{name}")
    issue = repo.get("issue")
    if not isinstance(issue, dict):
        raise WorkQueueError(f"Issue not found: #{number}")
    return _parse_issue(issue)


def is_ready(issue: QueueIssue) -> bool:
    return all(blocker.state == "CLOSED" for blocker in issue.blocked_by)


def is_in_progress(issue: QueueIssue) -> bool:
    return any(pr.state == "OPEN" for pr in issue.closing_prs)


def filter_issues(*, issues: list[QueueIssue], ready: bool) -> list[QueueIssue]:
    if not ready:
        return issues
    return [issue for issue in issues if is_ready(issue)]


def render_issue_rows(issues: list[QueueIssue]) -> str:
    header = "| issue | ready | in_progress | blocked_by | title |"
    divider = "|---:|:---:|:---:|---|---|"
    body: list[str] = []
    for issue in issues:
        ready = "yes" if is_ready(issue) else "no"
        in_progress = "yes" if is_in_progress(issue) else "no"
        blocked_by = " ".join(f"#{b.number}" for b in issue.blocked_by) or "(none)"
        body.append(
            f"| #{issue.issue_number} | {ready} | {in_progress} | {blocked_by} | {issue.title} |"
        )
    return "\n".join([header, divider, *body])


def render_pr_body(
    *,
    template_path: Path,
    issue: QueueIssue,
    specs_changed: str,
    tests_run: str,
) -> str:
    if not template_path.exists():
        return ""
    template = template_path.read_text(encoding="utf-8")
    return (
        template.replace("{{ISSUE_NUMBER}}", str(issue.issue_number))
        .replace("{{SPECS_CHANGED}}", specs_changed or "<fill>")
        .replace("{{TESTS_RUN}}", tests_run or "<fill>")
    )
