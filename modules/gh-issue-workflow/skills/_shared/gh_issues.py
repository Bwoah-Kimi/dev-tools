#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from gh_cli import GhCliError, extract_list, run


class GitHubIssueError(RuntimeError):
    pass


def _run(args: list[str], *, expect_json: bool = False, input_text: str | None = None) -> Any:
    try:
        return run(args, expect_json=expect_json, input_text=input_text)
    except GhCliError as exc:
        raise GitHubIssueError(str(exc)) from exc


def change_id_marker(change_id: str) -> str:
    return f"<!-- CHANGE_ID:{change_id} -->"


@dataclass
class IssueSummary:
    id: str
    number: int
    title: str
    url: str
    body: str
    state: str


def _extract_issue_url(output: str) -> str:
    match = re.search(r"https://github\.com/[^\s]+/issues/\d+", output)
    if match is None:
        raise GitHubIssueError(f"Could not parse issue URL from output:\n{output}")
    return match.group(0)


def _issue_number_from_url(url: str) -> int:
    match = re.search(r"/issues/(\d+)$", url.strip())
    if match is None:
        raise GitHubIssueError(f"Could not parse issue number from URL: {url}")
    return int(match.group(1))


def _as_summary(payload: dict[str, Any]) -> IssueSummary:
    issue_id = payload.get("id")
    number = payload.get("number")
    if not isinstance(number, int):
        if isinstance(number, float) and number.is_integer():
            number = int(number)
        else:
            raise GitHubIssueError(f"Invalid issue number: {number!r}")
    if not isinstance(issue_id, str) or not issue_id.strip():
        raise GitHubIssueError(f"Invalid issue id for #{number}: {issue_id!r}")
    title = payload.get("title") or f"#{number}"
    url = payload.get("url")
    if not isinstance(url, str):
        raise GitHubIssueError(f"Invalid issue URL for #{number}: {url!r}")
    body = payload.get("body")
    state = payload.get("state")
    return IssueSummary(
        id=issue_id.strip(),
        number=number,
        title=str(title),
        url=url,
        body=str(body or ""),
        state=str(state or "").upper(),
    )


def _is_exact_change_id_match(*, body: str, change_id: str) -> bool:
    return change_id_marker(change_id) in body


class GitHubIssueClient:
    def __init__(self, repo: str) -> None:
        self.repo = repo

    def _search(self, query: str) -> list[IssueSummary]:
        payload = _run(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                self.repo,
                "--state",
                "all",
                "--search",
                query,
                "--json",
                "id,number,title,url,body,state",
                "--limit",
                "100",
            ],
            expect_json=True,
        )
        return [_as_summary(row) for row in extract_list(payload, ())]

    @staticmethod
    def _dedupe(rows: list[IssueSummary]) -> list[IssueSummary]:
        by_number: dict[int, IssueSummary] = {}
        for row in rows:
            by_number[row.number] = row
        return sorted(by_number.values(), key=lambda row: row.number)

    @staticmethod
    def _canonical(rows: list[IssueSummary]) -> IssueSummary | None:
        if not rows:
            return None
        open_rows = [row for row in rows if row.state == "OPEN"]
        candidates = open_rows if open_rows else rows
        return sorted(candidates, key=lambda row: row.number)[0]

    def find_all_by_change_id(self, change_id: str) -> list[IssueSummary]:
        marker_query = f'"{change_id_marker(change_id)}" in:body'
        rows = [
            row
            for row in self._search(marker_query)
            if _is_exact_change_id_match(body=row.body, change_id=change_id)
        ]
        if rows:
            return self._dedupe(rows)
        return []

    def find_by_change_id(self, change_id: str) -> IssueSummary | None:
        return self._canonical(self.find_all_by_change_id(change_id))

    def upsert_by_change_id(
        self,
        *,
        change_id: str,
        title: str,
        body: str,
        upsert: bool,
    ) -> IssueSummary:
        if not upsert:
            return self.create_issue(title, body)
        existing = self.find_by_change_id(change_id)
        if existing is None:
            return self.create_issue(title, body)
        return self.edit_issue(existing.number, title, body)

    def create_issue(self, title: str, body: str) -> IssueSummary:
        output = _run(
            [
                "gh",
                "issue",
                "create",
                "--repo",
                self.repo,
                "--title",
                title,
                "--body-file",
                "-",
            ],
            input_text=body,
        )
        url = _extract_issue_url(output)
        return self.get_issue(_issue_number_from_url(url))

    def edit_issue(self, number: int, title: str, body: str) -> IssueSummary:
        _run(
            [
                "gh",
                "issue",
                "edit",
                str(number),
                "--repo",
                self.repo,
                "--title",
                title,
                "--body-file",
                "-",
            ],
            input_text=body,
        )
        return self.get_issue(number)

    def close_issue(self, number: int, *, comment: str, reason: str) -> None:
        args = [
            "gh",
            "issue",
            "close",
            str(number),
            "--repo",
            self.repo,
            "--reason",
            reason,
        ]
        if comment.strip():
            args.extend(["--comment", comment.strip()])
        _run(args)

    def get_issue(self, number: int) -> IssueSummary:
        payload = _run(
            [
                "gh",
                "issue",
                "view",
                str(number),
                "--repo",
                self.repo,
                "--json",
                "id,number,title,url,body,state",
            ],
            expect_json=True,
        )
        if not isinstance(payload, dict):
            raise GitHubIssueError(f"Unexpected issue payload for #{number}: {payload!r}")
        return _as_summary(payload)

    @staticmethod
    def set_issue_type(*, issue_id: str, issue_type_id: str) -> None:
        if not issue_id.strip():
            raise GitHubIssueError("set_issue_type requires non-empty issue_id")
        if not issue_type_id.strip():
            raise GitHubIssueError("set_issue_type requires non-empty issue_type_id")
        mutation = """
        mutation($id: ID!, $issueTypeId: ID!) {
          updateIssue(input: { id: $id, issueTypeId: $issueTypeId }) {
            issue { id }
          }
        }
        """.strip()
        payload = {
            "query": mutation,
            "variables": {"id": issue_id, "issueTypeId": issue_type_id},
        }
        result = _run(
            ["gh", "api", "graphql", "--input", "-"],
            expect_json=True,
            input_text=json.dumps(payload),
        )
        if not isinstance(result, dict):
            raise GitHubIssueError(f"Unexpected GraphQL payload: {result!r}")
        errors = result.get("errors")
        if isinstance(errors, list) and errors:
            raise GitHubIssueError(f"GraphQL updateIssue failed: {errors!r}")
