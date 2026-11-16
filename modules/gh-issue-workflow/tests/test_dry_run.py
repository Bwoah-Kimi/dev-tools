import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from test_spec_policy import bundle_without_impact

MODULE = Path(__file__).resolve().parents[1]
SYNC = MODULE / "skills" / "gh-sync-issues" / "scripts" / "gh_sync_plan.py"


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8", errors="replace")
        for path in root.rglob("*") if path.is_file()
    }


def install_fake_gh(repo: Path) -> tuple[dict[str, str], Path]:
    bin_dir = repo.parent / "fake-bin"
    bin_dir.mkdir(exist_ok=True)
    shutil.copy(MODULE / "tests" / "fixtures" / "gh_fake.py", bin_dir / "gh_fake.py")
    if os.name == "nt":
        shutil.copy(MODULE / "tests" / "fixtures" / "gh.cmd", bin_dir / "gh.cmd")
    else:
        wrapper = bin_dir / "gh"
        wrapper.write_text(
            '#!/bin/sh\nexec python3 "$(dirname "$0")/gh_fake.py" "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
    log = repo.parent / "gh-calls.jsonl"
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
    env["GH_FAKE_LOG"] = str(log)
    return env, log


def test_dry_run_does_not_create_archive_or_state(tmp_path, monkeypatch):
    repo = tmp_path
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    bundle = bundle_without_impact(repo)
    plan = repo / "plan.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    templates = repo / ".github" / "ISSUE_TEMPLATE"
    templates.mkdir(parents=True)
    shutil.copy(MODULE / "templates" / "parent_issue.yml", templates / "parent_issue.yml")
    shutil.copy(MODULE / "templates" / "sub_issue.yml", templates / "sub_issue.yml")
    env, log = install_fake_gh(repo)
    monkeypatch.setenv("PATH", env["PATH"])
    before = snapshot(repo)
    result = subprocess.run([
        sys.executable, str(SYNC), "--plan", str(plan), "--bundle", str(bundle),
        "--repo", "o/r", "--spec-mode", "none", "--dry-run"
    ], cwd=repo, env=env, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dry_run"] is True
    assert snapshot(repo) == before
    calls = [json.loads(line)["args"] for line in log.read_text(encoding="utf-8").splitlines()]
    forbidden = {"create", "edit", "delete", "merge", "POST", "PATCH", "DELETE"}
    assert all(not forbidden.intersection(args) for args in calls)
