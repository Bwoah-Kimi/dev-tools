import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "gh-workflow-init" / "scripts"))
from gh_workflow_doctor import run_doctor
from test_installer import make_git_repo


def fake_gh(args, input_text=None):
    if args[:2] == ["gh", "repo", "view"]:
        return {"nameWithOwner": "o/r", "name": "r", "owner": {"login": "o"}}
    if args[:3] == ["gh", "api", "graphql"]:
        return {"data": {"repository": {"issueTypes": {"nodes": [
            {"id": "type-feature", "name": "Feature"},
            {"id": "type-task", "name": "Task"},
        ]}}}}
    return ""


def recording_read_only_gh(calls):
    def runner(args, input_text=None):
        calls.append(args)
        return fake_gh(args, input_text)
    return runner


def test_local_doctor_reports_missing_template(tmp_path):
    repo = make_git_repo(tmp_path)
    report = run_doctor(repo, github=False, gh_runner=fake_gh)
    assert report["ok"] is False
    assert any("template" in finding for finding in report["findings"])


def test_github_doctor_uses_only_read_operations(tmp_path):
    repo = make_git_repo(tmp_path)
    calls = []
    report = run_doctor(repo, github=True, gh_runner=recording_read_only_gh(calls))
    assert calls
    for args in calls:
        assert "create" not in args and "edit" not in args and "merge" not in args
        assert "POST" not in args and "PATCH" not in args and "DELETE" not in args


def test_invalid_auth_is_reported(tmp_path):
    repo = make_git_repo(tmp_path)
    def denied(args, input_text=None):
        if args[:2] == ["gh", "auth", "status"]:
            raise RuntimeError("not authenticated")
        return fake_gh(args, input_text)
    report = run_doctor(repo, github=True, gh_runner=denied)
    assert any("auth" in finding for finding in report["findings"])
