#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass

from gh_cli import GhCliError
from gh_graphql import run_graphql


@dataclass(frozen=True)
class RepoInfo:
    id: str
    owner: str
    name: str
    name_with_owner: str


def fetch_repo(*, owner: str, name: str) -> RepoInfo:
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        id
        name
        nameWithOwner
        owner { login }
      }
    }
    """.strip()
    data = run_graphql(query=query, variables={"owner": owner, "name": name})
    repo = data.get("repository")
    if not isinstance(repo, dict):
        raise GhCliError(f"Repository not found: {owner}/{name}")
    repo_id = repo.get("id")
    repo_name = repo.get("name")
    repo_full = repo.get("nameWithOwner")
    repo_owner = (
        repo.get("owner", {}).get("login")
        if isinstance(repo.get("owner"), dict)
        else None
    )
    required_values = (repo_id, repo_name, repo_full, repo_owner)
    if not all(isinstance(v, str) and v.strip() for v in required_values):
        raise GhCliError(f"Invalid repository payload: {repo!r}")
    return RepoInfo(
        id=repo_id.strip(),
        owner=repo_owner.strip(),
        name=repo_name.strip(),
        name_with_owner=repo_full.strip(),
    )


def fetch_issue_type_ids(*, owner: str, name: str) -> dict[str, str]:
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        issueTypes(first: 100) {
          nodes { id name }
        }
      }
    }
    """.strip()
    data = run_graphql(query=query, variables={"owner": owner, "name": name})
    repo = data.get("repository")
    if not isinstance(repo, dict):
        raise GhCliError(f"Repository not found: {owner}/{name}")
    issue_types = repo.get("issueTypes", {})
    nodes = issue_types.get("nodes") if isinstance(issue_types, dict) else None
    if not isinstance(nodes, list):
        raise GhCliError(f"Repository issueTypes missing: {repo!r}")
    result: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        issue_type_id = node.get("id")
        issue_type_name = node.get("name")
        if (
            isinstance(issue_type_id, str)
            and isinstance(issue_type_name, str)
            and issue_type_id.strip()
            and issue_type_name.strip()
        ):
            result[issue_type_name.strip()] = issue_type_id.strip()
    return result


def require_issue_type_id(*, owner: str, name: str, issue_type_name: str) -> str:
    ids = fetch_issue_type_ids(owner=owner, name=name)
    issue_type_id = ids.get(issue_type_name)
    if issue_type_id:
        return issue_type_id
    available = ", ".join(sorted(ids)) or "(none)"
    raise GhCliError(
        f"Missing issue type {issue_type_name!r} in {owner}/{name}. "
        f"Available types: {available}"
    )
