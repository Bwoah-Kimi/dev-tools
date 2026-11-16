import importlib.util
import json
import subprocess
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
INSTALLER = MODULE / "install" / "gh_issue_workflow.py"


def make_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    return path


def run_install(repo: Path, action: str = "install", *extra: str):
    return subprocess.run([
        sys.executable, str(INSTALLER), action, "--repo", str(repo), *extra
    ], text=True, capture_output=True, check=False)


def load_installer():
    spec = importlib.util.spec_from_file_location("gh_issue_workflow_installer", INSTALLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_install_and_update_preserve_profile(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    result = run_install(repo)
    assert result.returncode == 0, result.stderr
    profile = repo / ".agents" / "gh-issue-workflow" / "config.json"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text('{"version": 1, "custom": true}\n', encoding="utf-8")
    managed = repo / ".agents" / "skills" / "_shared" / "issue_bundle.py"
    managed.write_text("# locally changed\n", encoding="utf-8")
    result = run_install(repo, "update")
    assert result.returncode != 0
    assert "managed file changed" in result.stderr
    assert profile.read_text(encoding="utf-8") == '{"version": 1, "custom": true}\n'


def test_dry_run_writes_nothing(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    before = set(repo.rglob("*"))
    result = run_install(repo, "install", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert set(repo.rglob("*")) == before


def test_repeated_install_is_idempotent(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    first = run_install(repo)
    assert first.returncode == 0, first.stderr
    manifest = repo / ".agents" / "gh-issue-workflow" / "managed-files.json"
    before = manifest.read_bytes()
    second = run_install(repo, "update")
    assert second.returncode == 0, second.stderr
    assert manifest.read_bytes() == before
    assert (repo / ".agents" / "skills" / "gh-workflow-init" / "SKILL.md").is_file()


def test_non_git_target_is_refused(tmp_path):
    target = tmp_path / "not-a-repo"
    target.mkdir()
    result = run_install(target)
    assert result.returncode != 0
    assert "Git repository" in result.stderr


def test_link_failure_is_actionable(tmp_path, monkeypatch):
    installer = load_installer()
    repo = make_git_repo(tmp_path / "repo")
    monkeypatch.setattr(installer, "_platform_link", lambda link, target: (_ for _ in ()).throw(OSError("denied")))
    try:
        installer.make_compatibility_link(repo, "claude", dry_run=False)
    except RuntimeError as exc:
        assert "claude" in str(exc)
        assert "symlink" in str(exc) or "junction" in str(exc)
    else:
        raise AssertionError("expected link failure")
