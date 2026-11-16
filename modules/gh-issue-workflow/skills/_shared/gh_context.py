#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from gh_cli import GhCliError, run
from workflow_config import discover_repo_root

DEFAULT_CONTEXT_PATH = Path("out/gh-skills/context.json")


@dataclass(frozen=True)
class GhContext:
    repo: str
    repo_owner: str
    repo_name: str
    host: str
    repo_root: str


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
    args.extend(["--json", "name,nameWithOwner,owner,url"])
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

    values = tuple(payload.get(key) for key in ("repo", "repo_owner", "repo_name", "host", "repo_root"))
    if not all(isinstance(value, str) and value.strip() for value in values):
        return None
    return GhContext(*(value.strip() for value in values))


def _write_context(path: Path, context: GhContext) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "repo": context.repo,
        "repo_owner": context.repo_owner,
        "repo_name": context.repo_name,
        "host": context.host,
        "repo_root": context.repo_root,
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def resolve_context(
    *,
    repo: str | None = None,
    repo_root: Path | None = None,
    context_path: Path | None = None,
    write_cache: bool = True,
) -> GhContext:
    root = (repo_root or discover_repo_root(Path.cwd())).resolve()
    cache_path = context_path or root / DEFAULT_CONTEXT_PATH
    cached = _load_context(cache_path)
    effective_repo = repo.strip() if isinstance(repo, str) and repo.strip() else ""

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
    raw_url = payload.get("url")
    host = urlsplit(raw_url).hostname if isinstance(raw_url, str) else None
    if not host:
        raise GhCliError("gh repo view did not return a valid repository URL.")

    context = GhContext(
        repo=effective_repo,
        repo_owner=repo_owner,
        repo_name=repo_name,
        host=host,
        repo_root=str(root),
    )
    if cached == context:
        return cached
    if write_cache:
        _write_context(cache_path, context)
    return context
