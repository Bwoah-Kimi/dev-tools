import json
from pathlib import Path

import pytest
from issue_bundle import IssueBundleError, load_issue_bundle
from spec_policy import validate_spec_path


def bundle_without_impact(tmp_path: Path) -> Path:
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps({
        "parent": {
            "title": "Plan", "objective": "Ship", "scope": [],
            "assumptions": [], "atom_registry": ["A1: Behavior"]
        },
        "items": [{
            "id": "S1", "title": "Task", "intent_and_contract": "Preserve behavior",
            "owned_atoms": ["A1: Behavior"], "implementation_plan": "Implement and test",
            "file_and_interface_scope": "src/module.py",
            "acceptance_checks": ["[A1] Behavior passes"]
        }]
    }), encoding="utf-8")
    return path


def test_none_policy_allows_missing_spec_impact(tmp_path):
    _, items, _ = load_issue_bundle(bundle_without_impact(tmp_path), spec_mode="none")
    assert items[0].spec_impact is None


def test_openspec_policy_still_requires_spec_impact(tmp_path):
    with pytest.raises(IssueBundleError, match="spec_impact"):
        load_issue_bundle(bundle_without_impact(tmp_path), spec_mode="openspec")


def test_optional_policy_still_requires_spec_impact(tmp_path):
    with pytest.raises(IssueBundleError, match="spec_impact"):
        load_issue_bundle(bundle_without_impact(tmp_path), spec_mode="optional")


def test_spec_path_rules():
    assert validate_spec_path("openspec/specs/cli/spec.md", "openspec", []) is None
    assert validate_spec_path("docs/design/cli.md", "optional", ["docs"]) is None
    assert validate_spec_path("docs/design/cli.md", "optional", []) is None
    assert validate_spec_path("../outside.md", "optional", []) is not None
    assert validate_spec_path("docs/design/cli.md", "openspec", []) is not None
