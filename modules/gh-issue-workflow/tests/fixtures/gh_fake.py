#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    log = os.environ.get("GH_FAKE_LOG")
    if log:
        with Path(log).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"args": args}) + "\n")
    forbidden = {"create", "edit", "delete", "merge", "POST", "PATCH", "DELETE"}
    if not os.environ.get("GH_FAKE_ALLOW_MUTATIONS") and forbidden.intersection(args):
        print("Mutation forbidden by fake gh", file=sys.stderr)
        return 97
    if args[:2] == ["repo", "view"]:
        repo = next((value for value in args[2:] if "/" in value), "o/r")
        owner, name = repo.split("/", 1)
        print(json.dumps({
            "nameWithOwner": repo,
            "name": name,
            "owner": {"login": owner},
            "url": f"https://github.com/{repo}",
        }))
        return 0
    if args[:3] == ["api", "graphql", "--input"]:
        payload = json.loads(sys.stdin.read())
        query = payload.get("query", "")
        variables = payload.get("variables", {})
        owner = variables.get("owner", "o")
        name = variables.get("name", "r")
        if "issueTypes" in query:
            data = {"repository": {"issueTypes": {"nodes": [
                {"id": "type-feature", "name": "Feature"},
                {"id": "type-task", "name": "Task"},
                {"id": "type-initiative", "name": "Initiative"},
                {"id": "type-work-item", "name": "Work Item"},
            ]}}}
        else:
            data = {"repository": {
                "id": "repo-o-r", "name": name, "nameWithOwner": f"{owner}/{name}",
                "owner": {"login": owner},
            }}
        print(json.dumps({"data": data}))
        return 0
    print(f"Unexpected fake gh call: {args!r}", file=sys.stderr)
    return 98


if __name__ == "__main__":
    raise SystemExit(main())
