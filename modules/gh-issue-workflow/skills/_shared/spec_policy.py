#!/usr/bin/env python3
from __future__ import annotations

from pathlib import PurePosixPath


def _relative_parts(value: str) -> tuple[str, ...] | None:
    path = PurePosixPath(value)
    if "\\" in value or path.is_absolute() or ".." in path.parts:
        return None
    return path.parts


def validate_spec_path(value: str, mode: str, roots: list[str]) -> str | None:
    parts = _relative_parts(value)
    if parts is None:
        return f"Spec path must be repository-relative and may not contain '..': {value}"
    if mode == "none":
        return None
    if mode == "openspec":
        if len(parts) >= 4 and parts[:2] == ("openspec", "specs") and parts[-1] == "spec.md":
            return None
        return f"Expected openspec/specs/**/spec.md: {value}"
    if roots and not any(value == root or value.startswith(root.rstrip("/") + "/") for root in roots):
        return f"Spec path is outside configured roots {roots}: {value}"
    return None
