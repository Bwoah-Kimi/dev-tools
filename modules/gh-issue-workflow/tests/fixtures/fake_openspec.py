#!/usr/bin/env python3
import sys
from pathlib import Path


def main() -> int:
    if sys.argv[1:] != ["validate", "--all", "--strict", "--no-interactive"]:
        print(f"unexpected arguments: {sys.argv[1:]}", file=sys.stderr)
        return 2
    specs = Path.cwd() / "openspec" / "specs"
    if not specs.is_dir() or not list(specs.glob("*/spec.md")):
        print("no OpenSpec specifications found", file=sys.stderr)
        return 1
    print("Fixture OpenSpec validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
