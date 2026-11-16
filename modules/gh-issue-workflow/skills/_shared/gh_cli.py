#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from typing import Any


class GhCliError(RuntimeError):
    pass


def run(
    args: list[str],
    *,
    expect_json: bool = False,
    input_text: str | None = None,
) -> Any:
    proc = subprocess.run(
        args,
        text=True,
        input=input_text,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise GhCliError(
            "Command failed "
            f"({proc.returncode}): {' '.join(args)}\n{proc.stderr.strip()}"
        )
    output = proc.stdout.strip()
    if not expect_json:
        return output
    if not output:
        return {}
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise GhCliError(f"Invalid JSON from command: {' '.join(args)}\n{output}") from exc


def extract_list(payload: Any, preferred_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in preferred_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        for value in payload.values():
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def parse_int(value: Any, *, label: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise GhCliError(f"Expected integer for {label}, got {value!r}")

