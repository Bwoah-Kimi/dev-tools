import subprocess
import sys
from pathlib import Path

import pytest
from approval import ApprovalError, load_approved_bundle, write_approval
from test_spec_policy import bundle_without_impact

SYNC = Path(__file__).resolve().parents[1] / "skills" / "gh-sync-issues" / "scripts" / "gh_sync_plan.py"


def test_approval_round_trip(tmp_path):
    bundle = {"parent": {"title": "P"}, "items": []}
    path = write_approval(tmp_path / "approved.json", bundle, "none")
    assert load_approved_bundle(path, bundle, "none") == bundle


def test_tampered_bundle_is_rejected(tmp_path):
    original = {"parent": {"title": "P"}, "items": []}
    path = write_approval(tmp_path / "approved.json", original, "none")
    changed = {"parent": {"title": "Changed"}, "items": []}
    with pytest.raises(ApprovalError, match="hash"):
        load_approved_bundle(path, changed, "none")


def test_policy_change_is_rejected(tmp_path):
    bundle = {"parent": {"title": "P"}, "items": []}
    path = write_approval(tmp_path / "approved.json", bundle, "none")
    with pytest.raises(ApprovalError, match="policy"):
        load_approved_bundle(path, bundle, "openspec")


def test_live_sync_requires_approval_before_any_writes(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    bundle = bundle_without_impact(tmp_path)
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    result = subprocess.run([
        sys.executable, str(SYNC), "--plan", str(plan), "--bundle", str(bundle),
        "--repo", "o/r", "--spec-mode", "none"
    ], cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 1
    assert "--approved-bundle is required" in result.stderr
    assert not (tmp_path / "out").exists()
