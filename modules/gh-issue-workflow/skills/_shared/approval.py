#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from issue_bundle import bundle_sha256


class ApprovalError(RuntimeError):
    pass


def write_approval(path: Path, bundle: dict, spec_mode: str) -> Path:
    payload = {
        "version": 1,
        "bundle_sha256": bundle_sha256(bundle),
        "spec_policy": spec_mode,
        "bundle": bundle,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApprovalError(f"Unable to read approval {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ApprovalError(f"Approval must be a JSON object: {path}")
    return payload


def load_approved_bundle(path: Path, current_bundle: dict, spec_mode: str) -> dict:
    payload = _read_json(path)
    if payload.get("version") != 1:
        raise ApprovalError(f"Unsupported approval version: {payload.get('version')!r}")
    if payload.get("spec_policy") != spec_mode:
        raise ApprovalError("Approved specification policy does not match current policy")
    if payload.get("bundle_sha256") != bundle_sha256(current_bundle):
        raise ApprovalError("Approved bundle hash does not match current bundle")
    if payload.get("bundle") != current_bundle:
        raise ApprovalError("Approved bundle content does not match current bundle")
    return current_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Write or verify an approved issue bundle")
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("write", "verify"):
        sub = subparsers.add_parser(action)
        sub.add_argument("--bundle", required=True, type=Path)
        sub.add_argument("--approved-bundle", required=True, type=Path)
        sub.add_argument(
            "--spec-mode", required=True, choices=("openspec", "optional", "none")
        )
    args = parser.parse_args()
    current = _read_json(args.bundle)
    try:
        if args.action == "write":
            write_approval(args.approved_bundle, current, args.spec_mode)
            print(args.approved_bundle)
        else:
            load_approved_bundle(args.approved_bundle, current, args.spec_mode)
            print(f"Approval OK: {args.approved_bundle}")
    except ApprovalError as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
