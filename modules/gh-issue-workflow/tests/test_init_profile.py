import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "gh-workflow-init" / "scripts"))
from gh_workflow_profile import ProfileError, write_profile
from test_installer import make_git_repo


def test_profile_contains_explicit_policy_and_references(tmp_path):
    repo = make_git_repo(tmp_path)
    (repo / "AGENTS.md").write_text("# Rules\nRun project tests.\n", encoding="utf-8")
    write_profile(repo, {
        "issue_types": {"parent": "Initiative", "work": "Work Item"},
        "spec_policy": {"mode": "none", "roots": []},
        "validation": {"setup": [], "commands": ["python -m pytest"]},
        "required_documents": ["AGENTS.md"],
    }, confirmed=True)
    config = json.loads((repo / ".agents/gh-issue-workflow/config.json").read_text())
    assert config["issue_types"]["work"] == "Work Item"
    context = (repo / ".agents/gh-issue-workflow/project-context.md").read_text()
    assert "[AGENTS.md](../../AGENTS.md)" in context


def test_existing_profile_requires_reviewed_change_set(tmp_path):
    repo = make_git_repo(tmp_path)
    profile = repo / ".agents/gh-issue-workflow/config.json"
    profile.parent.mkdir(parents=True)
    profile.write_text('{"version": 1, "custom": true}\n', encoding="utf-8")
    with pytest.raises(ProfileError, match="reviewed change set"):
        write_profile(repo, {"version": 1}, confirmed=True)


def test_unconfirmed_init_writes_nothing(tmp_path):
    repo = make_git_repo(tmp_path)
    with pytest.raises(ProfileError, match="confirmation"):
        write_profile(repo, {"spec_policy": {"mode": "none"}}, confirmed=False)
    assert not (repo / ".agents").exists()
