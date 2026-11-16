from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".codex/skills/_shared"))

import issue_bundle as ib  # noqa: E402
import issue_form as issue_form_module  # noqa: E402

VALIDATOR = ROOT / ".agents/skills/gh-plan-to-issues/scripts/gh_validate_bundle.py"


def _form() -> issue_form_module.IssueForm:
    return issue_form_module.IssueForm(
        path=ROOT / ".github/ISSUE_TEMPLATE/sub_issue.yml",
        name="Sub-issue",
        fields=[
            issue_form_module.IssueFormField(
                id="spec_impact", label="Expected Spec Impact", type="textarea"
            )
        ],
    )


def _item(*, item_id: str = "S1", spec_impact: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item_id,
        "title": f"[Sub] Task {item_id}",
        "intent_and_contract": "Preserve the approved contract.",
        "owned_atoms": ["A1: Owns the behavior contract."],
        "spec_impact": spec_impact,
        "implementation_plan": "Implement and test, then reconcile the canonical spec.",
        "file_and_interface_scope": "openspec/specs/project-docs/spec.md",
        "acceptance_checks": ["[A1] The approved behavior is implemented."],
        "assumptions_defaults": "(none)",
        "references": ["openspec/specs/project-docs/spec.md"],
        "handoff_contract": "(none)",
        "dependencies": [],
    }


def _impact() -> dict[str, Any]:
    return {
        "rationale": "The README behavior contract likely needs reconciliation.",
        "spec_paths": ["openspec/specs/project-docs/spec.md"],
    }


def _bundle(*items: dict[str, Any]) -> dict[str, Any]:
    return {
        "parent": {
            "title": "[Plan] Workflow",
            "objective": "Keep the workflow executable.",
            "scope": [],
            "assumptions": [],
            "atom_registry": ["A1: The workflow contract remains current."],
        },
        "items": list(items),
    }


def _write_bundle(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _validate(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--bundle", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_bundle_renders_expected_spec_impact(tmp_path: Path) -> None:
    bundle_path = _write_bundle(tmp_path, _bundle(_item(spec_impact=_impact())))
    _, items, _ = ib.load_issue_bundle(bundle_path)

    body = issue_form_module.render_sub_issue_body(
        form=_form(),
        change_id="plan-run-S1",
        item=items[0],
        dependencies_text="",
    )

    assert "## Expected Spec Impact" in body
    assert "The README behavior contract likely needs reconciliation." in body
    assert "- `openspec/specs/project-docs/spec.md`" in body


def test_bundle_renders_explicit_no_spec_impact(tmp_path: Path) -> None:
    impact = {
        "rationale": "Existing behavior contracts should remain unchanged.",
        "spec_paths": [],
    }
    bundle_path = _write_bundle(tmp_path, _bundle(_item(spec_impact=impact)))
    _, items, _ = ib.load_issue_bundle(bundle_path)

    body = issue_form_module.render_sub_issue_body(
        form=_form(),
        change_id="plan-run-S1",
        item=items[0],
        dependencies_text="",
    )

    assert "Existing behavior contracts should remain unchanged." in body
    assert "Expected canonical specs:\n- (none)" in body


def test_validator_accepts_expected_spec_path(tmp_path: Path) -> None:
    path = _write_bundle(tmp_path, _bundle(_item(spec_impact=_impact())))
    result = _validate(path)
    assert result.returncode == 0, result.stderr
    assert "1 expected spec paths" in result.stdout


def test_validator_rejects_noncanonical_spec_path(tmp_path: Path) -> None:
    impact = _impact()
    impact["spec_paths"][0] = "docs/spec.md"
    path = _write_bundle(tmp_path, _bundle(_item(spec_impact=impact)))
    result = _validate(path)
    assert result.returncode == 1
    assert "must be a canonical openspec/specs/**/spec.md path" in result.stderr


def test_validator_warns_about_cross_task_spec_overlap(tmp_path: Path) -> None:
    path = _write_bundle(
        tmp_path,
        _bundle(
            _item(item_id="S1", spec_impact=_impact()),
            _item(item_id="S2", spec_impact=_impact()),
        ),
    )
    result = _validate(path)
    assert result.returncode == 0, result.stderr
    assert "shared by Tasks S1, S2" in result.stdout
    assert "encode an ordering dependency if needed" in result.stdout
