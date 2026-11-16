from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "skills" / "gh-work-queue" / "scripts"))

import gh_work_queue as cli  # noqa: E402
import work_queue_model as wq  # noqa: E402


def _task_issue(number: int) -> wq.QueueIssue:
    return wq.QueueIssue(
        issue_id=f"id-{number}",
        issue_number=number,
        title=f"Task {number}",
        url=f"https://github.com/o/r/issues/{number}",
        body="Task body",
        state="OPEN",
        issue_type="Task",
        blocked_by=[],
        closing_prs=[],
    )


def test_cmd_show_json_includes_parent_issue(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "fetch_issue", lambda owner, name, number: _task_issue(number))
    monkeypatch.setattr(
        cli,
        "fetch_parent_issue",
        lambda owner, name, number: wq.ParentIssue(
            number=7,
            title="Feature parent",
            url="https://github.com/o/r/issues/7",
            body="Parent body",
        ),
    )
    args = argparse.Namespace(repo_owner="o", repo_name="r", issue=42, format="json")
    assert cli._cmd_show(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["issue_number"] == 42
    assert payload["parent_issue"] == {
        "number": 7,
        "title": "Feature parent",
        "url": "https://github.com/o/r/issues/7",
        "body": "Parent body",
    }


def test_cmd_show_json_uses_null_parent_when_missing(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "fetch_issue", lambda owner, name, number: _task_issue(number))
    monkeypatch.setattr(cli, "fetch_parent_issue", lambda owner, name, number: None)
    args = argparse.Namespace(repo_owner="o", repo_name="r", issue=42, format="json")
    assert cli._cmd_show(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["parent_issue"] is None
