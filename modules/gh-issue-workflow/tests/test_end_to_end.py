import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1]
FIXTURES = MODULE / "tests" / "fixtures"


@dataclass
class FlowResult:
    returncode: int
    stderr: str
    repo: Path
    profile: dict
    dry_run_files_unchanged: bool
    queue_rows: list[str]
    pr_body: str
    validated_commands: list[str]


def run_fixture_flow(repo: Path) -> FlowResult:
    env = os.environ.copy()
    env["GH_WORKFLOW_MODULE"] = str(MODULE)
    completed = subprocess.run(
        [sys.executable, str(repo / "fixture_driver.py")],
        cwd=repo, env=env, text=True, capture_output=True, check=False,
    )
    result_path = repo.parent / "acceptance-result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
    profile_path = repo / ".agents" / "gh-issue-workflow" / "config.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    return FlowResult(
        returncode=completed.returncode,
        stderr=completed.stderr,
        repo=repo,
        profile=profile,
        dry_run_files_unchanged=bool(payload.get("dry_run_files_unchanged", False)),
        queue_rows=list(payload.get("queue_rows", [])),
        pr_body=str(payload.get("pr_body", "")),
        validated_commands=list(payload.get("validated_commands", [])),
    )


def fixture_repo(source: str, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURES / source, repo)
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    return repo


@pytest.fixture
def no_spec_repo(tmp_path):
    return fixture_repo("no-spec", tmp_path)


@pytest.fixture
def with_openspec_repo(tmp_path):
    return fixture_repo("with-openspec", tmp_path)


def test_no_spec_repository_lifecycle(no_spec_repo):
    result = run_fixture_flow(no_spec_repo)
    assert result.returncode == 0, result.stderr
    assert result.profile["spec_policy"]["mode"] == "none"
    assert not (result.repo / "out").exists() or result.dry_run_files_unchanged
    assert result.queue_rows == ["#2"]
    assert "Resolves #2" in result.pr_body
    assert "Fixes #2" not in result.pr_body


def test_openspec_repository_lifecycle(with_openspec_repo):
    result = run_fixture_flow(with_openspec_repo)
    assert result.returncode == 0, result.stderr
    assert result.profile["spec_policy"]["mode"] == "openspec"
    assert "openspec validate --all --strict --no-interactive" in result.validated_commands
    assert result.queue_rows == ["#2"]
