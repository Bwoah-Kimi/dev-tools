#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
MANAGED_SKILLS = (
    "gh-plan-to-issues", "gh-sync-issues", "gh-work-queue", "_shared",
)
MANIFEST = Path(".agents/gh-issue-workflow/managed-files.json")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_repository(repo: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        text=True, capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Target is not a Git repository: {repo}: {result.stderr.strip()}")
    return Path(result.stdout.strip()).resolve()


def copy_tree(source: Path, target: Path, relative_root: Path, hashes: dict[str, str], dry_run: bool) -> None:
    if not source.is_dir():
        raise RuntimeError(f"Managed source is missing: {source}")
    if not dry_run:
        shutil.copytree(source, target, dirs_exist_ok=True)
    for path in source.rglob("*"):
        if path.is_file():
            relative = path.relative_to(relative_root)
            hashes[relative.as_posix()] = file_sha256(path)


def copy_managed(module: Path, repo: Path, dry_run: bool) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name in MANAGED_SKILLS:
        copy_tree(
            module / "skills" / name,
            repo / ".agents" / "skills" / name,
            module / "skills",
            hashes,
            dry_run,
        )
    # Store canonical .agents/skills paths in the manifest.
    hashes = {(Path(".agents/skills") / Path(key)).as_posix(): value for key, value in hashes.items()}
    for host, suffix in (("claude", "*.md"), ("codex", "*.toml")):
        source = module / "agents" / host
        target = repo / f".{host}" / "agents"
        for path in source.glob(suffix):
            relative = Path(f".{host}/agents") / path.name
            if not dry_run:
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target / path.name)
            hashes[relative.as_posix()] = file_sha256(path)
    return hashes


def _platform_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            text=True, capture_output=True, check=False,
        )
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or result.stdout.strip())
        return
    relative = os.path.relpath(target, link.parent)
    link.symlink_to(Path(relative), target_is_directory=True)


def make_compatibility_link(repo: Path, host: str, dry_run: bool) -> None:
    if host not in {"claude", "codex"}:
        raise ValueError(host)
    link = repo / f".{host}" / "skills"
    target = repo / ".agents" / "skills"
    if dry_run:
        print(f"link {link} -> {target}")
        return
    if os.path.lexists(link):
        try:
            if link.resolve() == target.resolve() and (link.is_symlink() or link.is_junction()):
                return
        except OSError:
            pass
        raise RuntimeError(f"Compatibility path already exists and is not a managed link: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        _platform_link(link, target)
    except (OSError, RuntimeError) as exc:
        raise RuntimeError(
            f"Unable to create {host} skills symlink/junction at {link}: {exc}. "
            "Enable symlink or directory-junction support, then rerun install."
        ) from exc


def verify_manifest(repo: Path) -> None:
    path = repo / MANIFEST
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    for relative, expected in payload.get("files", {}).items():
        installed = repo / relative
        if not installed.is_file() or file_sha256(installed) != expected:
            raise RuntimeError(
                f"managed file changed: {relative}. Restore it or move local changes "
                "outside managed paths before updating."
            )


def ensure_no_unowned_overwrite(repo: Path) -> None:
    if (repo / MANIFEST).exists():
        return
    for name in MANAGED_SKILLS:
        target = repo / ".agents" / "skills" / name
        if target.exists():
            raise RuntimeError(f"Managed target exists without a manifest: {target}")


def run_filesystem_action(repo: Path, action: str, dry_run: bool) -> None:
    root = validate_repository(repo)
    verify_manifest(root)
    ensure_no_unowned_overwrite(root)
    hashes = copy_managed(MODULE_ROOT, root, dry_run)
    for host in ("claude", "codex"):
        make_compatibility_link(root, host, dry_run)
    if not dry_run:
        path = root / MANIFEST
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"version": 1, "files": hashes}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(f"{action} {'preview' if dry_run else 'complete'}: {root}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or update GitHub Issue workflow skills")
    parser.add_argument("action", choices=("install", "update"))
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        run_filesystem_action(args.repo, args.action, args.dry_run)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
