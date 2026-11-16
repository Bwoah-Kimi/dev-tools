#!/usr/bin/env python3
from __future__ import annotations

from gh_cli import GhCliError
from gh_graphql import run_graphql


def fetch_blocked_by_ids(*, issue_id: str) -> set[str]:
    if not issue_id:
        raise GhCliError("fetch_blocked_by_ids requires non-empty issue_id")
    query = """
    query($id: ID!) {
      node(id: $id) {
        __typename
        ... on Issue {
          blockedBy(first: 100) {
            nodes { id }
          }
        }
      }
    }
    """.strip()
    data = run_graphql(query=query, variables={"id": issue_id})
    node = data.get("node")
    if not isinstance(node, dict) or node.get("__typename") != "Issue":
        raise GhCliError(f"Expected Issue node for id {issue_id!r}, got: {node!r}")
    blocked_by = node.get("blockedBy", {})
    nodes = blocked_by.get("nodes") if isinstance(blocked_by, dict) else None
    if not isinstance(nodes, list):
        return set()
    ids: set[str] = set()
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        blocker_id = raw.get("id")
        if isinstance(blocker_id, str) and blocker_id.strip():
            ids.add(blocker_id.strip())
    return ids


def _mutate(*, name: str, issue_id: str, blocking_issue_id: str) -> None:
    mutation = f"""
    mutation($issueId: ID!, $blockingIssueId: ID!) {{
      {name}(input: {{ issueId: $issueId, blockingIssueId: $blockingIssueId }}) {{
        clientMutationId
      }}
    }}
    """.strip()
    run_graphql(
        query=mutation,
        variables={"issueId": issue_id, "blockingIssueId": blocking_issue_id},
    )


def reconcile_blocked_by(*, issue_id: str, desired_blocker_ids: set[str]) -> None:
    existing = fetch_blocked_by_ids(issue_id=issue_id)
    desired = {bid.strip() for bid in desired_blocker_ids if bid.strip()}
    to_add = sorted(desired - existing)
    to_remove = sorted(existing - desired)
    for blocker_id in to_remove:
        _mutate(
            name="removeBlockedBy",
            issue_id=issue_id,
            blocking_issue_id=blocker_id,
        )
    for blocker_id in to_add:
        _mutate(
            name="addBlockedBy",
            issue_id=issue_id,
            blocking_issue_id=blocker_id,
        )

