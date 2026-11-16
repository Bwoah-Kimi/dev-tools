import copy
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from approval import write_approval
from test_dry_run import install_fake_gh
from workflow_config import DEFAULT_CONFIG

SYNC = Path(__file__).resolve().parents[1] / "skills" / "gh-sync-issues" / "scripts" / "gh_sync_plan.py"


def work_item(item_id: str, atom: str, dependencies: list[str]) -> dict:
    return {
        "id": item_id,
        "title": f"Work {item_id}",
        "intent_and_contract": f"Deliver {atom}",
        "owned_atoms": [f"{atom}: {item_id} owns behavior"],
        "implementation_plan": "Implement and test",
        "file_and_interface_scope": "src/module.py",
        "acceptance_checks": [f"[{atom}] Behavior passes"],
        "assumptions_defaults": "(none)",
        "references": [],
        "handoff_contract": "(none)",
        "dependencies": dependencies,
    }


@pytest.fixture
def sync_env(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    template_dir = repo / ".github" / "ISSUE_TEMPLATE"
    template_dir.mkdir(parents=True)
    module = Path(__file__).resolve().parents[1]
    for name in ("parent_issue.yml", "sub_issue.yml"):
        (template_dir / name).write_text(
            (module / "templates" / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["issue_types"] = {"parent": "Initiative", "work": "Work Item"}
    config["spec_policy"] = {"mode": "none", "roots": []}
    config_path = repo / ".agents" / "gh-issue-workflow" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    plan = repo / "plan.md"
    plan.write_text("# Two work items\n", encoding="utf-8")
    bundle = repo / "bundle.json"
    payload = {
        "parent": {
            "title": "Plan", "objective": "Deliver both", "scope": [],
            "assumptions": [], "atom_registry": ["A1: First", "A2: Second"],
        },
        "items": [work_item("S1", "A1", []), work_item("S2", "A2", ["S1"])],
    }
    bundle.write_text(json.dumps(payload), encoding="utf-8")
    approved = write_approval(repo / "review" / "approved.json", payload, "none")
    environment, gh_log = install_fake_gh(repo)
    environment["GH_FAKE_ALLOW_MUTATIONS"] = "1"
    environment["GH_FAKE_STATE"] = str(tmp_path / "github-state.json")
    monkeypatch.setenv("PATH", environment["PATH"])
    return SimpleNamespace(
        repo=repo, plan=plan, bundle=bundle, approved=approved,
        environment=environment, gh_log=gh_log,
    )


def run_sync(env, approved: bool):
    args = [
        sys.executable, str(SYNC), "--repo", "o/r",
        "--plan", str(env.plan), "--bundle", str(env.bundle),
        "--config", str(env.repo / ".agents/gh-issue-workflow/config.json"),
    ]
    if approved:
        args.extend(["--approved-bundle", str(env.approved)])
    else:
        args.append("--dry-run")
    return subprocess.run(
        args, cwd=env.repo, env=env.environment,
        text=True, capture_output=True, check=False,
    )


def read_gh_calls(env) -> list[dict]:
    if not env.gh_log.exists():
        return []
    return [json.loads(line) for line in env.gh_log.read_text(encoding="utf-8").splitlines()]


def test_sync_uses_configured_types_and_native_dependencies(sync_env):
    result = run_sync(sync_env, approved=True)
    assert result.returncode == 0, result.stderr
    calls = read_gh_calls(sync_env)
    typed = [call for call in calls if call["op"] == "set-type"]
    assert any(call["role"] == "parent" and call["issue_type"] == "Initiative" for call in typed)
    work = [call for call in typed if call["role"] == "work"]
    assert {call["issue_type"] for call in work} == {"Work Item"}
    blocked = [call for call in calls if call["op"] == "blocked-by"]
    assert [(call["item"], call["blocker"]) for call in blocked] == [("S2", "S1")]


def test_second_sync_resumes_without_duplicate_issues(sync_env):
    first = run_sync(sync_env, approved=True)
    assert first.returncode == 0, first.stderr
    second = run_sync(sync_env, approved=True)
    assert second.returncode == 0, second.stderr
    creates = [call for call in read_gh_calls(sync_env) if call["op"].startswith("create-")]
    assert len(creates) == 3
