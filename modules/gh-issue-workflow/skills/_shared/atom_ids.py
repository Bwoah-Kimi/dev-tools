#!/usr/bin/env python3
from __future__ import annotations

import re

ATOM_ID_RE = re.compile(r"^(A\d+)\s*:")


def atom_id_from_line(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("-"):
        stripped = stripped.lstrip("-").strip()
    match = ATOM_ID_RE.match(stripped)
    return match.group(1) if match else ""
