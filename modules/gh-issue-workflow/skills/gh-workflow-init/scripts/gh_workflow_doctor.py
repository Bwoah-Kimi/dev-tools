#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from workflow_doctor import run_doctor

__all__ = ["run_doctor"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only workflow configuration checks")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--github", action="store_true")
    args = parser.parse_args()
    report = run_doctor(args.repo, args.github)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
