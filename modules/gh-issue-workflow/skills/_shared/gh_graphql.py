#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any

from gh_cli import GhCliError, run


def run_graphql(*, query: str, variables: dict[str, object] | None = None) -> dict[str, Any]:
    payload = {"query": query, "variables": variables or {}}
    raw = run(
        ["gh", "api", "graphql", "--input", "-"],
        expect_json=True,
        input_text=json.dumps(payload),
    )
    if not isinstance(raw, dict):
        raise GhCliError(f"Unexpected GraphQL payload: {raw!r}")
    errors = raw.get("errors")
    if isinstance(errors, list) and errors:
        # Keep the error payload compact but actionable.
        messages = []
        for err in errors:
            if isinstance(err, dict) and isinstance(err.get("message"), str):
                messages.append(err["message"])
        suffix = "\n".join(messages) if messages else str(errors)
        raise GhCliError(f"GraphQL query failed:\n{suffix}")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise GhCliError(f"GraphQL response missing data: {raw!r}")
    return data

