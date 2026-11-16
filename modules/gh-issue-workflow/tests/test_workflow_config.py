import json
import subprocess
from pathlib import Path

import pytest
from workflow_config import ConfigError, DEFAULT_CONFIG, discover_repo_root, load_config


def init_repo(path: Path) -> Path:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    return path


def test_config_loads_repository_profile(tmp_path):
    repo = init_repo(tmp_path)
    profile = repo / ".agents" / "gh-issue-workflow"
    profile.mkdir(parents=True)
    (profile / "config.json").write_text(json.dumps({
        "version": 1,
        "spec_policy": {"mode": "none", "roots": []},
        "issue_types": {"parent": "Initiative", "work": "Work Item"},
        "paths": {"cache": "artifacts/github-cache"}
    }), encoding="utf-8")
    config = load_config(repo)
    assert config.parent_issue_type == "Initiative"
    assert config.work_issue_type == "Work Item"
    assert config.spec_mode == "none"
    assert config.output_path("cache") == repo / "artifacts" / "github-cache"


def test_discovery_works_from_a_subdirectory(tmp_path):
    repo = init_repo(tmp_path)
    nested = repo / "src" / "nested"
    nested.mkdir(parents=True)
    assert discover_repo_root(nested) == repo.resolve()


def test_unknown_spec_mode_fails(tmp_path):
    repo = init_repo(tmp_path)
    with pytest.raises(ConfigError, match="spec_policy.mode"):
        load_config(repo, overrides={"spec_policy": {"mode": "automatic"}})


def test_default_config_matches_template():
    template = Path(__file__).resolve().parents[1] / "templates" / "config.json"
    assert DEFAULT_CONFIG == json.loads(template.read_text(encoding="utf-8"))


def test_output_path_cannot_escape_repository(tmp_path):
    repo = init_repo(tmp_path)
    config = load_config(repo, overrides={"paths": {"cache": "../outside"}})
    with pytest.raises(ConfigError, match="escapes repository"):
        config.output_path("cache")
