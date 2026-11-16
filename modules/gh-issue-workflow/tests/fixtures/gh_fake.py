#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

TYPE_IDS = {
    "Feature": "type-feature",
    "Task": "type-task",
    "Initiative": "type-initiative",
    "Work Item": "type-work-item",
}
TYPE_NAMES = {value: key for key, value in TYPE_IDS.items()}


def load_state() -> dict:
    path = os.environ.get("GH_FAKE_STATE")
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {"next_number": 1, "issues": [], "blocked_by": {}, "sub_issues": {}}


def save_state(state: dict) -> None:
    path = os.environ.get("GH_FAKE_STATE")
    if path:
        Path(path).write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def record(op: str, args: list[str], **extra) -> None:
    path = os.environ.get("GH_FAKE_LOG")
    if path:
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"op": op, "args": args, **extra}) + "\n")


def issue_by_id(state: dict, issue_id: str) -> dict:
    return next(issue for issue in state["issues"] if issue["id"] == issue_id)


def issue_by_number(state: dict, number: int) -> dict:
    return next(issue for issue in state["issues"] if issue["number"] == number)


def summary(issue: dict) -> dict:
    return {key: issue[key] for key in ("id", "number", "title", "url", "body", "state")}


def queue_node(issue: dict, state: dict) -> dict:
    blockers = []
    for issue_id in state["blocked_by"].get(issue["id"], []):
        blocker = issue_by_id(state, issue_id)
        blockers.append({"number": blocker["number"], "state": blocker["state"], "url": blocker["url"]})
    type_name = TYPE_NAMES.get(issue.get("issue_type_id"), "")
    return {
        **summary(issue),
        "issueType": {"name": type_name},
        "blockedBy": {"nodes": blockers},
        "closedByPullRequestsReferences": {"nodes": []},
    }


def arg_value(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1]


def graphql(args: list[str], state: dict) -> int:
    payload = json.loads(sys.stdin.read())
    query = payload.get("query", "")
    variables = payload.get("variables", {})
    if "issues(" in query:
        nodes = [queue_node(issue, state) for issue in state["issues"] if issue["state"] == "OPEN"]
        data = {"repository": {"issues": {
            "nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None},
        }}}
    elif "issue(number:" in query:
        issue = issue_by_number(state, int(variables["number"]))
        data = {"repository": {"issue": queue_node(issue, state)}}
    elif "issueTypes" in query:
        data = {"repository": {"issueTypes": {"nodes": [
            {"id": value, "name": key} for key, value in TYPE_IDS.items()
        ]}}}
    elif "updateIssue" in query:
        issue = issue_by_id(state, variables["id"])
        issue["issue_type_id"] = variables["issueTypeId"]
        save_state(state)
        record(
            "set-type", args, item=issue.get("item_id"), role=issue["role"],
            issue_type=TYPE_NAMES[variables["issueTypeId"]],
        )
        data = {"updateIssue": {"issue": {"id": issue["id"]}}}
    elif "node(id:" in query and "blockedBy" in query:
        issue_id = variables["id"]
        nodes = [{"id": value} for value in state["blocked_by"].get(issue_id, [])]
        data = {"node": {"__typename": "Issue", "blockedBy": {"nodes": nodes}}}
    elif "addBlockedBy" in query or "removeBlockedBy" in query:
        issue = issue_by_id(state, variables["issueId"])
        blocker = issue_by_id(state, variables["blockingIssueId"])
        existing = state["blocked_by"].setdefault(issue["id"], [])
        if "addBlockedBy" in query and blocker["id"] not in existing:
            existing.append(blocker["id"])
        if "removeBlockedBy" in query and blocker["id"] in existing:
            existing.remove(blocker["id"])
        save_state(state)
        record("blocked-by", args, item=issue.get("item_id"), blocker=blocker.get("item_id"))
        name = "addBlockedBy" if "addBlockedBy" in query else "removeBlockedBy"
        data = {name: {"clientMutationId": "fake"}}
    else:
        owner = variables.get("owner", "o")
        name = variables.get("name", "r")
        data = {"repository": {
            "id": "repo-o-r", "name": name, "nameWithOwner": f"{owner}/{name}",
            "owner": {"login": owner},
        }}
    print(json.dumps({"data": data}))
    return 0


def issue_command(args: list[str], state: dict) -> int:
    action = args[1]
    if action == "list":
        record("list", args)
        print(json.dumps([summary(issue) for issue in state["issues"]]))
        return 0
    if action == "create":
        number = state["next_number"]
        state["next_number"] += 1
        title = arg_value(args, "--title")
        body = sys.stdin.read()
        role = "parent" if "PLAN_ROLE:PARENT" in body else "work"
        item_match = re.search(r"PLAN_ITEM:([^\s]+)", body)
        issue = {
            "id": f"issue-{number}", "number": number, "title": title,
            "url": f"https://github.com/o/r/issues/{number}", "body": body,
            "state": "OPEN", "rest_id": number * 1000, "role": role,
            "item_id": item_match.group(1) if item_match else None,
        }
        state["issues"].append(issue)
        save_state(state)
        record(f"create-{role}", args, item=issue["item_id"])
        print(issue["url"])
        return 0
    number = int(args[2])
    issue = issue_by_number(state, number)
    if action == "view":
        record("view", args)
        print(json.dumps(summary(issue)))
        return 0
    if action == "edit":
        issue["title"] = arg_value(args, "--title")
        issue["body"] = sys.stdin.read()
        save_state(state)
        record("edit", args, item=issue.get("item_id"))
        return 0
    if action == "close":
        issue["state"] = "CLOSED"
        save_state(state)
        record("close", args, item=issue.get("item_id"))
        return 0
    raise AssertionError(args)


def rest_command(args: list[str], state: dict) -> int:
    path = next(value for value in args if value.startswith("repos/"))
    match = re.fullmatch(r"repos/o/r/issues/(\d+)(?:/(sub_issues|sub_issue))?", path)
    if not match:
        raise AssertionError(args)
    number = int(match.group(1))
    relation = match.group(2)
    if relation is None:
        issue = issue_by_number(state, number)
        record("rest-id", args, item=issue.get("item_id"))
        print(json.dumps({"id": issue["rest_id"]}))
        return 0
    parent = issue_by_number(state, number)
    children = state["sub_issues"].setdefault(parent["id"], [])
    if relation == "sub_issues" and "-X" not in args:
        rows = [issue_by_id(state, child) for child in children]
        print(json.dumps([{"id": row["rest_id"], "number": row["number"]} for row in rows]))
        return 0
    child_rest_id = int(arg_value(args, "-F").split("=", 1)[1])
    child = next(issue for issue in state["issues"] if issue["rest_id"] == child_rest_id)
    if relation == "sub_issues" and arg_value(args, "-X") == "POST":
        if child["id"] not in children:
            children.append(child["id"])
        record("sub-issue-add", args, parent=parent["number"], child=child["number"])
    else:
        if child["id"] in children:
            children.remove(child["id"])
        record("sub-issue-remove", args, parent=parent["number"], child=child["number"])
    save_state(state)
    return 0


def main() -> int:
    args = sys.argv[1:]
    state = load_state()
    forbidden = {"create", "edit", "delete", "merge", "POST", "PATCH", "DELETE"}
    if not os.environ.get("GH_FAKE_ALLOW_MUTATIONS") and forbidden.intersection(args):
        record("forbidden", args)
        print("Mutation forbidden by fake gh", file=sys.stderr)
        return 97
    try:
        if args[:2] == ["repo", "view"]:
            repo = next((value for value in args[2:] if "/" in value), "o/r")
            owner, name = repo.split("/", 1)
            record("repo-view", args)
            print(json.dumps({
                "nameWithOwner": repo, "name": name, "owner": {"login": owner},
                "url": f"https://github.com/{repo}",
            }))
            return 0
        if args[:3] == ["api", "graphql", "--input"]:
            return graphql(args, state)
        if args[:2] == ["api", "graphql"] and "-f" in args:
            return graphql(args, state)
        if args and args[0] == "issue":
            return issue_command(args, state)
        if args and args[0] == "api":
            return rest_command(args, state)
    except (AssertionError, StopIteration, KeyError, ValueError) as exc:
        record("error", args, error=str(exc))
        print(f"Unexpected fake gh call: {args!r}: {exc}", file=sys.stderr)
        return 98
    record("error", args)
    print(f"Unexpected fake gh call: {args!r}", file=sys.stderr)
    return 98


if __name__ == "__main__":
    raise SystemExit(main())
