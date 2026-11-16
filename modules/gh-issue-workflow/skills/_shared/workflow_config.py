#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    pass


DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "issue_types": {"parent": "Feature", "work": "Task"},
    "templates": {
        "parent": ".github/ISSUE_TEMPLATE/parent_issue.yml",
        "work": ".github/ISSUE_TEMPLATE/sub_issue.yml",
        "pr": ".github/pull_request_template.md",
    },
    "fields": {
        "parent": {
            "objective": "objective",
            "scope": "scope",
            "assumptions": "assumptions",
            "atom_registry": "atom_registry",
            "coverage_matrix": "coverage_matrix",
        },
        "work": {
            "intent_and_contract": "intent_and_contract",
            "owned_atoms": "owned_atoms",
            "spec_impact": "spec_impact",
            "implementation_plan": "implementation_plan",
            "file_and_interface_scope": "file_and_interface_scope",
            "acceptance_checks": "acceptance_checks",
            "assumptions_defaults": "assumptions_defaults",
            "references": "references",
            "handoff_contract": "handoff_contract",
            "dependencies": "dependencies",
        },
    },
    "spec_policy": {"mode": "none", "roots": []},
    "validation": {"setup": [], "commands": []},
    "agents": {
        "preflight": "gh-preflight",
        "bundle_reviewer": "gh-bundle-reviewer",
        "environment": "gh-validation-runner",
        "implementer": "gh-implementer",
        "spec_reviewer": "gh-spec-reviewer",
        "code_reviewer": "gh-code-reviewer",
        "merge_closer": "gh-merge-closer",
    },
    "paths": {
        "plan": "out/gh-plan-to-issues",
        "queue": "out/gh-work-queue",
        "cache": "out/gh-skills",
    },
    "pr_policy": {"close_keyword": "Fixes", "merge": "opt-in", "allow_admin": False},
}

_ALLOWED_KEYS = {
    "version", "issue_types", "templates", "fields", "spec_policy",
    "validation", "agents", "paths", "pr_policy",
}


def discover_repo_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ConfigError(f"Not inside a Git repository: {start}: {result.stderr.strip()}")
    return Path(result.stdout.strip()).resolve()


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


@dataclass(frozen=True)
class WorkflowConfig:
    repo_root: Path
    data: dict[str, Any]

    @property
    def parent_issue_type(self) -> str:
        return str(self.data["issue_types"]["parent"])

    @property
    def work_issue_type(self) -> str:
        return str(self.data["issue_types"]["work"])

    @property
    def spec_mode(self) -> str:
        return str(self.data["spec_policy"]["mode"])

    @property
    def spec_roots(self) -> list[str]:
        return list(self.data["spec_policy"].get("roots", []))

    def output_path(self, name: str) -> Path:
        value = Path(self.data["paths"][name])
        path = value if value.is_absolute() else self.repo_root / value
        resolved = path.resolve()
        if resolved != self.repo_root and self.repo_root not in resolved.parents:
            raise ConfigError(f"Output path escapes repository: {value}")
        return resolved

    def template_path(self, name: str) -> Path:
        value = Path(self.data["templates"][name])
        path = value if value.is_absolute() else self.repo_root / value
        return path.resolve()


def _read_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Unable to load config {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"Config must be a JSON object: {path}")
    unknown = set(payload) - _ALLOWED_KEYS
    if unknown:
        raise ConfigError(f"Unknown config keys in {path}: {', '.join(sorted(unknown))}")
    return payload


def load_config(
    repo_root: Path,
    overrides: dict[str, Any] | None = None,
    *,
    config_path: Path | None = None,
) -> WorkflowConfig:
    root = discover_repo_root(repo_root)
    path = config_path or root / ".agents" / "gh-issue-workflow" / "config.json"
    profile = _read_profile(path)
    merged = _merge(DEFAULT_CONFIG, profile)
    if overrides:
        merged = _merge(merged, overrides)
    if merged["spec_policy"]["mode"] not in {"openspec", "optional", "none"}:
        raise ConfigError("spec_policy.mode must be openspec, optional, or none")
    if merged.get("version") != 1:
        raise ConfigError(f"Unsupported config version: {merged.get('version')!r}")
    return WorkflowConfig(repo_root=root, data=merged)
