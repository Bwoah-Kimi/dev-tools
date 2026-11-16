#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from gh_cli import GhCliError, run


def _extract_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        raw_items = (
            payload.get("items") or payload.get("sub_issues") or payload.get("data")
        )
        if isinstance(raw_items, list):
            return [item for item in raw_items if isinstance(item, dict)]
    return []


def issue_rest_id(*, repo: str, issue_number: int) -> int:
    payload = run(
        ["gh", "api", f"repos/{repo}/issues/{issue_number}"],
        expect_json=True,
    )
    if not isinstance(payload, dict):
        raise GhCliError(
            f"Unexpected payload for issue #{issue_number}: {payload!r}"
        )
    raw_id = payload.get("id")
    if isinstance(raw_id, int):
        return raw_id
    if isinstance(raw_id, float) and raw_id.is_integer():
        return int(raw_id)
    raise GhCliError(
        f"Unable to resolve REST id for issue #{issue_number}: {raw_id!r}"
    )


def list_sub_issues(*, repo: str, parent_number: int) -> list[dict[str, Any]]:
    payload = run(
        ["gh", "api", f"repos/{repo}/issues/{parent_number}/sub_issues"],
        expect_json=True,
    )
    return _extract_list(payload)


def add_sub_issue(*, repo: str, parent_number: int, sub_issue_id: int) -> None:
    try:
        run(
            [
                "gh",
                "api",
                "-X",
                "POST",
                f"repos/{repo}/issues/{parent_number}/sub_issues",
                "-F",
                f"sub_issue_id={sub_issue_id}",
            ]
        )
    except GhCliError as exc:
        message = str(exc).lower()
        if "already" in message and ("sub-issue" in message or "sub issue" in message):
            return
        raise


def remove_sub_issue(*, repo: str, parent_number: int, sub_issue_id: int) -> None:
    try:
        run(
            [
                "gh",
                "api",
                "-X",
                "DELETE",
                f"repos/{repo}/issues/{parent_number}/sub_issue",
                "-F",
                f"sub_issue_id={sub_issue_id}",
            ]
        )
    except GhCliError as exc:
        message = str(exc).lower()
        if "not found" in message or "does not exist" in message:
            return
        raise
