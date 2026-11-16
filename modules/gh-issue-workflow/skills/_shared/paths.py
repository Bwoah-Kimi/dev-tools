#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parent.parent

SETUP_HINT = f"Setup/prerequisites: see {SKILLS_ROOT}/README.md"


def sanitize_component(value: str) -> str:
    raw = value.strip()
    if not raw:
        return "x"
    raw = re.sub(r"\s+", "-", raw)
    raw = re.sub(r"[^A-Za-z0-9._-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    return raw or "x"
