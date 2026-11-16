#!/usr/bin/env python3
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8", errors="replace")
        for path in root.rglob("*") if path.is_file()
    }


def main() -> int:
    repo = Path(__file__).resolve().parent
    module = Path(os.environ["GH_WORKFLOW_MODULE"])
    env = os.environ.copy()
    env["GH_WORKFLOW_MODULE"] = str(module)
    env["GH_WORKFLOW_GH"] = f"{sys.executable} {module / 'tests/fixtures/gh_fake.py'}"
    env["GH_FAKE_ALLOW_MUTATIONS"] = "1"
    env["GH_FAKE_STATE"] = str(repo.parent / "github-state.json")
    env["GH_FAKE_LOG"] = str(repo.parent / "gh-calls.jsonl")

    def run(args: list[str]) -> subprocess.CompletedProcess:
        completed = subprocess.run(
            args, cwd=repo, env=env, text=True, capture_output=True, check=False
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Command failed: {args}\n{completed.stderr}\n{completed.stdout}")
        return completed

    run([
        sys.executable, str(module / "install/gh_issue_workflow.py"),
        "install", "--repo", str(repo),
    ])
    answers = json.loads((repo / "init_answers.json").read_text(encoding="utf-8"))
    spec_mode = answers["spec_policy"]["mode"]
    run([
        sys.executable,
        str(repo / ".agents/skills/gh-workflow-init/scripts/gh_workflow_profile.py"),
        "--repo", str(repo), "--answers", str(repo / "init_answers.json"), "--confirmed",
    ])
    template_dir = repo / ".github" / "ISSUE_TEMPLATE"
    template_dir.mkdir(parents=True, exist_ok=True)
    for name in ("parent_issue.yml", "sub_issue.yml"):
        shutil.copy(module / "templates" / name, template_dir / name)
    shutil.copy(
        module / "templates" / "pull_request_template.md",
        repo / ".github" / "pull_request_template.md",
    )
    run([
        sys.executable,
        str(repo / ".agents/skills/gh-workflow-init/scripts/gh_workflow_doctor.py"),
        "--repo", str(repo),
    ])

    plan = repo / "plan.md"
    bundle = repo / "bundle.json"
    validator_args = [
        sys.executable,
        str(repo / ".agents/skills/gh-plan-to-issues/scripts/gh_validate_bundle.py"),
        "--bundle", str(bundle), "--spec-mode", spec_mode,
    ]
    for root in answers["spec_policy"].get("roots", []):
        validator_args.extend(["--spec-root", root])
    run(validator_args)

    sync = repo / ".agents/skills/gh-sync-issues/scripts/gh_sync_plan.py"
    before = snapshot(repo)
    run([
        sys.executable, str(sync), "--repo", "o/r", "--plan", str(plan),
        "--bundle", str(bundle), "--dry-run",
    ])
    dry_run_unchanged = snapshot(repo) == before
    if not dry_run_unchanged:
        raise RuntimeError("dry-run changed repository files")

    approved = repo / "review" / "approved-bundle.json"
    run([
        sys.executable, str(repo / ".agents/skills/_shared/approval.py"), "write",
        "--bundle", str(bundle), "--approved-bundle", str(approved),
        "--spec-mode", spec_mode,
    ])
    run([
        sys.executable, str(sync), "--repo", "o/r", "--plan", str(plan),
        "--bundle", str(bundle), "--approved-bundle", str(approved),
    ])

    state_path = Path(env["GH_FAKE_STATE"])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    for issue in state["issues"]:
        if issue.get("item_id") == "S1":
            issue["state"] = "CLOSED"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    queue_script = repo / ".agents/skills/gh-work-queue/scripts/gh_work_queue.py"
    queue = run([
        sys.executable, str(queue_script), "list", "--ready", "--format", "json",
        "--repo", "o/r",
    ])
    queue_rows = [f"#{row['issue_number']}" for row in json.loads(queue.stdout)]

    validated_commands = list(answers.get("validation", {}).get("commands", []))
    for command in validated_commands:
        run(shlex.split(command, posix=os.name != "nt"))
    if spec_mode == "openspec":
        canonical = "openspec validate --all --strict --no-interactive"
        validated_commands.append(canonical)
        run([
            sys.executable, str(module / "tests/fixtures/fake_openspec.py"),
            "validate", "--all", "--strict", "--no-interactive",
        ])

    specs_changed = (
        "openspec/specs/cli/spec.md" if spec_mode == "openspec"
        else "(none; repository policy none)"
    )
    pr = run([
        sys.executable, str(queue_script), "pr-body", "--issue", "2", "--repo", "o/r",
        "--specs-changed", specs_changed, "--tests-run", "\n".join(validated_commands),
    ])
    result = {
        "dry_run_files_unchanged": dry_run_unchanged,
        "queue_rows": queue_rows,
        "pr_body": pr.stdout,
        "validated_commands": validated_commands,
    }
    (repo.parent / "acceptance-result.json").write_text(json.dumps(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
