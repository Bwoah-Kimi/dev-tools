import json

import pytest
from gh_context import resolve_context
from gh_issues import GitHubIssueError, extract_issue_url


def test_cache_cannot_override_current_repo(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "repo": "old/project", "repo_owner": "old", "repo_name": "project",
        "host": "github.com", "repo_root": str(tmp_path / "old")
    }), encoding="utf-8")
    monkeypatch.setattr("gh_context._repo_view", lambda repo: {
        "nameWithOwner": "new/current", "name": "current",
        "owner": {"login": "new"}, "url": "https://github.com/new/current"
    })
    context = resolve_context(repo_root=tmp_path, context_path=cache)
    assert context.repo == "new/current"


def test_dry_resolution_does_not_write_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("gh_context._repo_view", lambda repo: {
        "nameWithOwner": "o/r", "name": "r", "owner": "o",
        "url": "https://git.example.com/o/r"
    })
    cache = tmp_path / "cache.json"
    context = resolve_context(repo_root=tmp_path, context_path=cache, write_cache=False)
    assert context.host == "git.example.com"
    assert not cache.exists()


def test_matching_cache_is_reused_without_network(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "repo": "o/r", "repo_owner": "o", "repo_name": "r",
        "host": "github.com", "repo_root": str(tmp_path.resolve())
    }), encoding="utf-8")
    monkeypatch.setattr("gh_context._repo_view", lambda repo: {
        "nameWithOwner": "o/r", "name": "r", "owner": "o",
        "url": "https://github.com/o/r"
    })
    context = resolve_context(repo_root=tmp_path, context_path=cache)
    assert context.repo == "o/r"


def test_enterprise_issue_url():
    output = "Created https://git.example.com/acme/tools/issues/42\n"
    assert extract_issue_url(output, "git.example.com") == "https://git.example.com/acme/tools/issues/42"
    with pytest.raises(GitHubIssueError):
        extract_issue_url(output, "other.example.com")
