from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".codex/skills/_shared"))

import work_queue_model as wq  # noqa: E402


def _issue(*, number: int, blocked_by: list[wq.BlockedByRef]) -> wq.QueueIssue:
    return wq.QueueIssue(
        issue_id=f"id-{number}",
        issue_number=number,
        title=f"t-{number}",
        url="u",
        body="",
        state="OPEN",
        issue_type="Task",
        blocked_by=blocked_by,
        closing_prs=[],
    )


def test_is_ready_requires_all_blockers_closed() -> None:
    blocked = _issue(
        number=1,
        blocked_by=[
            wq.BlockedByRef(number=10, state="CLOSED", url="u"),
            wq.BlockedByRef(number=11, state="OPEN", url="u"),
        ],
    )
    assert not wq.is_ready(blocked)

    ready = _issue(
        number=2,
        blocked_by=[
            wq.BlockedByRef(number=20, state="CLOSED", url="u"),
            wq.BlockedByRef(number=21, state="CLOSED", url="u"),
        ],
    )
    assert wq.is_ready(ready)

    unblocked = _issue(number=3, blocked_by=[])
    assert wq.is_ready(unblocked)


def test_filter_issues_ready_filters_only_ready() -> None:
    issues = [
        _issue(
            number=1,
            blocked_by=[wq.BlockedByRef(number=10, state="OPEN", url="u")],
        ),
        _issue(
            number=2,
            blocked_by=[wq.BlockedByRef(number=20, state="CLOSED", url="u")],
        ),
    ]
    filtered = wq.filter_issues(issues=issues, ready=True)
    assert [issue.issue_number for issue in filtered] == [2]

    unfiltered = wq.filter_issues(issues=issues, ready=False)
    assert [issue.issue_number for issue in unfiltered] == [1, 2]


def test_is_in_progress_detects_open_prs() -> None:
    issue = _issue(number=1, blocked_by=[])
    assert not wq.is_in_progress(issue)

    in_progress = wq.QueueIssue(
        issue_id="id-2",
        issue_number=2,
        title="t-2",
        url="u",
        body="",
        state="OPEN",
        issue_type="Task",
        blocked_by=[],
        closing_prs=[wq.ClosingPrRef(number=123, state="OPEN", url="u")],
    )
    assert wq.is_in_progress(in_progress)


def test_render_issue_rows_uses_issue_identity() -> None:
    rows = wq.render_issue_rows([_issue(number=42, blocked_by=[])])
    assert "| issue | ready | in_progress | blocked_by | title |" in rows
    assert "| #42 | yes | no | (none) | t-42 |" in rows


def test_render_pr_body_lists_reconciled_specs(tmp_path: Path) -> None:
    template = tmp_path / "pull_request_template.md"
    template.write_text(
        "Fixes #{{ISSUE_NUMBER}}\n{{SPECS_CHANGED}}\n{{TESTS_RUN}}\n",
        encoding="utf-8",
    )
    body = wq.render_pr_body(
        template_path=template,
        issue=_issue(number=42, blocked_by=[]),
        specs_changed="- `openspec/specs/example/spec.md`",
        tests_run="- `pytest`",
    )
    assert body == ("Fixes #42\n- `openspec/specs/example/spec.md`\n- `pytest`\n")


def test_render_pr_body_does_not_infer_no_spec_change(tmp_path: Path) -> None:
    template = tmp_path / "pull_request_template.md"
    template.write_text("{{SPECS_CHANGED}}\n", encoding="utf-8")

    body = wq.render_pr_body(
        template_path=template,
        issue=_issue(number=42, blocked_by=[]),
        specs_changed="",
        tests_run="",
    )

    assert body == "<fill>\n"


def test_fetch_parent_issue_returns_parent_issue(monkeypatch) -> None:
    def fake_run(args: list[str], *, expect_json: bool = False, input_text: str | None = None):
        assert expect_json is True
        assert input_text is None
        assert args == ["gh", "api", "repos/o/r/issues/42/parent"]
        return {
            "number": 7,
            "title": "Feature parent",
            "html_url": "https://github.com/o/r/issues/7",
            "body": "Parent body",
        }

    monkeypatch.setattr(wq, "run", fake_run)
    parent = wq.fetch_parent_issue(owner="o", name="r", number=42)
    assert parent == wq.ParentIssue(
        number=7,
        title="Feature parent",
        url="https://github.com/o/r/issues/7",
        body="Parent body",
    )


def test_fetch_parent_issue_returns_none_when_missing(monkeypatch) -> None:
    def fake_run(args: list[str], *, expect_json: bool = False, input_text: str | None = None):
        raise wq.GhCliError("Command failed (404): gh api repos/o/r/issues/42/parent\nNot Found")

    monkeypatch.setattr(wq, "run", fake_run)
    assert wq.fetch_parent_issue(owner="o", name="r", number=42) is None
