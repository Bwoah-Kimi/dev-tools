#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path
from typing import Any, Callable

from gh_cli import run
from issue_form import IssueFormError, load_issue_form, mapped_field_ids, require_field_ids
from workflow_config import ConfigError, discover_repo_root, load_config

GhRunner = Callable[..., Any]


def _default_gh_runner(args: list[str], input_text: str | None = None) -> Any:
    expect_json = "--json" in args or (args[:2] == ["gh", "api"])
    return run(args, expect_json=expect_json, input_text=input_text)


def _check_links(root: Path, findings: list[str]) -> None:
    target = (root / ".agents" / "skills").resolve()
    for host in ("claude", "codex"):
        link = root / f".{host}" / "skills"
        if not os.path.lexists(link):
            findings.append(f"missing compatibility link: {link}")
            continue
        if not (link.is_symlink() or link.is_junction()) or link.resolve() != target:
            findings.append(f"compatibility link does not resolve to .agents/skills: {link}")


def _check_validation(config, findings: list[str]) -> None:
    for group in ("setup", "commands"):
        values = config.data.get("validation", {}).get(group, [])
        if not isinstance(values, list):
            findings.append(f"validation.{group} must be a list")
            continue
        for command in values:
            if not isinstance(command, str) or not shlex.split(command):
                findings.append(f"validation.{group} contains an empty or invalid command: {command!r}")


def _check_project_context(root: Path, findings: list[str]) -> None:
    path = root / ".agents" / "gh-issue-workflow" / "project-context.md"
    if not path.is_file():
        findings.append("missing project-context.md; run gh-workflow-init")
        return
    text = path.read_text(encoding="utf-8")
    for link in re.findall(r"\]\(([^)]+)\)", text):
        if "://" in link or link.startswith("#"):
            continue
        target = (path.parent / link).resolve()
        if not target.is_file():
            findings.append(f"project context reference missing: {link}")


def _github_checks(config, repo: str | None, gh_runner: GhRunner, findings: list[str]) -> None:
    try:
        gh_runner(["gh", "--version"])
        gh_runner(["gh", "auth", "status"])
    except Exception as exc:
        findings.append(f"gh auth or CLI check failed: {exc}")
        return
    try:
        payload = gh_runner([
            "gh", "repo", "view", *([repo] if repo else []),
            "--json", "name,nameWithOwner,owner,url",
        ])
        resolved = payload.get("nameWithOwner")
        if not isinstance(resolved, str) or "/" not in resolved:
            findings.append("GitHub repository resolution did not return nameWithOwner")
            return
    except Exception as exc:
        findings.append(f"GitHub repository resolution failed: {exc}")
        return
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        issueTypes(first: 100) { nodes { id name } }
      }
    }
    """.strip()
    try:
        owner, name = resolved.split("/", 1)
        payload = gh_runner(
            ["gh", "api", "graphql", "--input", "-"],
            input_text=json.dumps({"query": query, "variables": {"owner": owner, "name": name}}),
        )
        nodes = payload.get("data", {}).get("repository", {}).get("issueTypes", {}).get("nodes", [])
        available = {node.get("name") for node in nodes if isinstance(node, dict)}
        for expected in (config.parent_issue_type, config.work_issue_type):
            if expected not in available:
                findings.append(f"GitHub Issue Type missing: {expected}")
    except Exception as exc:
        findings.append(f"GitHub Issue Type probe failed: {exc}")
    try:
        issues = gh_runner(["gh", "api", f"repos/{resolved}/issues?per_page=1"])
        if isinstance(issues, list) and issues and isinstance(issues[0], dict):
            number = issues[0].get("number")
            if isinstance(number, int):
                gh_runner(["gh", "api", f"repos/{resolved}/issues/{number}/sub_issues"])
        else:
            findings.append("native sub-issue probe needs an existing issue in the repository")
    except Exception as exc:
        findings.append(f"native sub-issue API probe failed: {exc}")


def run_doctor(
    repo_root: Path,
    github: bool,
    gh_runner: GhRunner | None = None,
    repo: str | None = None,
) -> dict:
    findings: list[str] = []
    try:
        root = discover_repo_root(repo_root)
    except ConfigError as exc:
        return {"ok": False, "findings": [str(exc)]}
    config_path = root / ".agents" / "gh-issue-workflow" / "config.json"
    if not config_path.is_file():
        findings.append("missing config.json; run gh-workflow-init")
    try:
        config = load_config(root, config_path=config_path)
    except (ConfigError, OSError, json.JSONDecodeError) as exc:
        findings.append(f"invalid configuration: {exc}")
        return {"ok": False, "findings": findings}

    for role in ("parent", "work"):
        path = config.template_path(role)
        if not path.is_file():
            findings.append(f"{role} template missing: {path}")
            continue
        try:
            form = load_issue_form(path)
            require_field_ids(
                form=form,
                required=mapped_field_ids(config.data["fields"], role, config.spec_mode),
            )
        except IssueFormError as exc:
            findings.append(str(exc))
    pr_template = config.template_path("pr")
    if not pr_template.is_file():
        findings.append(f"PR template missing: {pr_template}")
    for name in ("plan", "queue", "cache"):
        try:
            config.output_path(name)
        except ConfigError as exc:
            findings.append(str(exc))
    _check_validation(config, findings)
    _check_project_context(root, findings)
    _check_links(root, findings)
    if github:
        _github_checks(config, repo, gh_runner or _default_gh_runner, findings)
    return {"ok": not findings, "findings": findings}
