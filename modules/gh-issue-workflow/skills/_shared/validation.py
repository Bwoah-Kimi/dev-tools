#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise ValueError(f"Expected object for {label}, got {value!r}")


def require_str(value: Any, label: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(f"Expected non-empty string for {label}, got {value!r}")


def require_int(value: Any, label: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ValueError(f"Expected int for {label}, got {value!r}")


def optional_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
