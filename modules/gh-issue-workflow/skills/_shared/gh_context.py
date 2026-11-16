#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gh_cli import GhCliError, run

DEFAULT_CONTEXT_PATH = Path("out/gh-skills/context.json")


@dataclass(frozen=True)
class GhContext:
    repo: str
    repo_owner: str
    repo_name: str


def _extract_repo_owner(payload: dict[str, Any]) -> str:
    owner = payload.get("owner")
    if isinstance(owner, dict):
        login = owner.get("login")
        if isinstance(login, str) and login.strip():
            return login.strip()
    if isinstance(owner, str) and owner.strip():
        return owner.strip()
    return ""


def _repo_view(repo: str | None) -> dict[str, Any]:
    args = ["gh", "repo", "view"]
    if repo:
        args.append(repo)
    args.extend(["--json", "name,nameWithOwner,owner"])
    try:
        payload = run(args, expect_json=True)
    except GhCliError as exc:
        hint = (
            "Failed to resolve repo context. Run this from inside a git clone "
            "or pass --repo OWNER/REPO."
        )
        raise GhCliError(f"{exc}\n{hint}") from exc
    if not isinstance(payload, dict):
        raise GhCliError(f"Unexpected gh repo view payload: {payload!r}")
    return payload


def _load_context(path: Path) -> GhContext | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise GhCliError(f"Invalid gh-skills context file: {path}") from exc
    if not isinstance(payload, dict):
        raise GhCliError(f"Invalid gh-skills context payload: {path}")

    repo = payload.get("repo")
    repo_owner = payload.get("repo_owner")
    repo_name = payload.get("repo_name")
    values = (repo, repo_owner, repo_name)
    if not all(isinstance(value, str) and value.strip() for value in values):
        return None
    return GhContext(
        repo=repo.strip(),
        repo_owner=repo_owner.strip(),
        repo_name=repo_name.strip(),
    )


def _write_context(path: Path, context: GhContext) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "repo": context.repo,
        "repo_owner": context.repo_owner,
        "repo_name": context.repo_name,
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def resolve_context(
    *,
    repo: str | None = None,
    context_path: Path = DEFAULT_CONTEXT_PATH,
) -> GhContext:
    cached = _load_context(context_path)
    effective_repo = repo.strip() if isinstance(repo, str) and repo.strip() else ""
    if cached is not None:
        if not effective_repo:
            return cached
        if cached.repo == effective_repo:
            return cached

    payload = _repo_view(effective_repo or None)
    name_with_owner = payload.get("nameWithOwner")
    repo_name = payload.get("name")
    if not effective_repo:
        if not isinstance(name_with_owner, str) or not name_with_owner.strip():
            raise GhCliError("gh repo view did not return nameWithOwner.")
        effective_repo = name_with_owner.strip()

    if not isinstance(repo_name, str) or not repo_name.strip():
        raise GhCliError("gh repo view did not return repo name.")
    repo_name = repo_name.strip()
    repo_owner = _extract_repo_owner(payload)
    if not repo_owner:
        raise GhCliError("gh repo view did not return repo owner login.")

    context = GhContext(
        repo=effective_repo,
        repo_owner=repo_owner,
        repo_name=repo_name,
    )
    _write_context(context_path, context)
    return context
