#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from workflow_config import DEFAULT_CONFIG, _merge, discover_repo_root


class ProfileError(RuntimeError):
    pass


def _safe_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ProfileError(f"Required document must be repository-relative: {value}")
    return path.as_posix()


def _validate_answers(repo: Path, answers: dict) -> None:
    mode = answers.get("spec_policy", {}).get("mode", "none")
    if mode not in {"openspec", "optional", "none"}:
        raise ProfileError("spec_policy.mode must be openspec, optional, or none")
    for document in answers.get("required_documents", []):
        relative = _safe_relative_path(document)
        if not (repo / relative).is_file():
            raise ProfileError(f"Required document does not exist: {relative}")
    for command in answers.get("validation", {}).get("commands", []):
        if not isinstance(command, str) or not shlex.split(command):
            raise ProfileError(f"Validation command must be a nonempty string: {command!r}")


def _context_markdown(answers: dict) -> str:
    documents = [_safe_relative_path(value) for value in answers.get("required_documents", [])]
    constraints = answers.get("constraints", [])
    commands = answers.get("validation", {}).get("commands", [])
    lines = ["# Repository Workflow Context", "", "## Normative Documents", ""]
    lines.extend(f"- [{document}](../../{document})" for document in documents)
    if not documents:
        lines.append("- No additional normative documents were confirmed.")
    lines.extend(["", "## Required Validation", ""])
    lines.extend(f"- `{command}`" for command in commands)
    if not commands:
        lines.append("- No repository-specific validation commands were confirmed.")
    lines.extend(["", "## Repository Constraints", ""])
    lines.extend(f"- {constraint}" for constraint in constraints)
    if not constraints:
        lines.append("- No additional repository-specific constraints were confirmed.")
    return "\n".join(lines) + "\n"


def write_profile(
    repo: Path,
    answers: dict,
    confirmed: bool = False,
    reviewed_change_set: bool = False,
    dry_run: bool = False,
) -> tuple[Path, Path]:
    root = discover_repo_root(repo)
    profile_dir = root / ".agents" / "gh-issue-workflow"
    config_path = profile_dir / "config.json"
    context_path = profile_dir / "project-context.md"
    if dry_run:
        print(f"preview profile: {config_path}")
        print(f"preview context: {context_path}")
        return config_path, context_path
    if not confirmed:
        raise ProfileError("Profile writes require explicit confirmation")
    if (config_path.exists() or context_path.exists()) and not reviewed_change_set:
        raise ProfileError("Existing profile requires a reviewed change set")
    _validate_answers(root, answers)

    current = {}
    if config_path.exists():
        current = json.loads(config_path.read_text(encoding="utf-8"))
    settings = {
        key: value for key, value in answers.items()
        if key not in {"required_documents", "constraints"}
    }
    config = _merge(current or DEFAULT_CONFIG, settings)
    profile_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    context_path.write_text(_context_markdown(answers), encoding="utf-8")
    return config_path, context_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a reviewed repository workflow profile")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--answers", required=True, type=Path)
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--reviewed-change-set", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        answers = json.loads(args.answers.read_text(encoding="utf-8"))
        if not isinstance(answers, dict):
            raise ProfileError("Answers must be a JSON object")
        write_profile(
            args.repo, answers, confirmed=args.confirmed,
            reviewed_change_set=args.reviewed_change_set, dry_run=args.dry_run,
        )
    except (OSError, json.JSONDecodeError, ProfileError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
