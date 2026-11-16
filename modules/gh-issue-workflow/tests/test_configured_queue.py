import argparse
import json

import pytest
from work_queue_model import WorkQueueError, list_open_task_issues, render_pr_body
from test_work_queue_model import _issue


def test_queue_uses_configured_work_type(monkeypatch):
    def raw_issue(number: int, type_name: str) -> dict:
        return {
            "id": f"id-{number}", "number": number, "title": f"t-{number}",
            "url": f"https://github.com/o/r/issues/{number}", "body": "", "state": "OPEN",
            "issueType": {"name": type_name}, "blockedBy": {"nodes": []},
            "closedByPullRequestsReferences": {"nodes": []},
        }

    monkeypatch.setattr("work_queue_model.run_graphql", lambda **kwargs: {
        "repository": {"issues": {
            "nodes": [raw_issue(1, "Task"), raw_issue(2, "Work Item")],
            "pageInfo": {"hasNextPage": False},
        }}
    })
    issues = list_open_task_issues(owner="o", name="r", work_issue_type="Work Item")
    assert [issue.issue_number for issue in issues] == [2]


def test_pr_template_uses_configured_close_keyword(tmp_path):
    template = tmp_path / "pr.md"
    template.write_text("{{CLOSE_KEYWORD}} #{{ISSUE_NUMBER}}\n{{TESTS_RUN}}\n", encoding="utf-8")
    body = render_pr_body(
        template_path=template, issue=_issue(number=42, blocked_by=[]),
        specs_changed="(none; documentation only)", tests_run="- `pytest`",
        close_keyword="Resolves"
    )
    assert body.startswith("Resolves #42\n")


def test_show_rejects_unexpected_configured_type(monkeypatch):
    import gh_work_queue as cli

    issue = _issue(number=42, blocked_by=[])
    monkeypatch.setattr(cli, "fetch_issue", lambda owner, name, number: issue)
    args = argparse.Namespace(
        repo_owner="o", repo_name="r", issue=42, format="json",
        expected_issue_type="Work Item",
    )
    with pytest.raises(WorkQueueError, match="Work Item"):
        cli._cmd_show(args)
