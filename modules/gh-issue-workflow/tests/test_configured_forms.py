import yaml
from issue_form import (
    load_issue_form,
    mapped_field_ids,
    render_sub_issue_body,
)
from issue_bundle import load_issue_bundle
from test_spec_policy import bundle_without_impact


def test_none_policy_omits_spec_field(tmp_path):
    _, items, _ = load_issue_bundle(bundle_without_impact(tmp_path), spec_mode="none")
    form_path = tmp_path / "form.yml"
    form_path.write_text(yaml.safe_dump({
        "name": "Work", "description": "Work item", "body": [{
            "type": "textarea", "id": "intent_and_contract",
            "attributes": {"label": "Intent"}
        }]
    }), encoding="utf-8")
    body = render_sub_issue_body(
        form_path=form_path, change_id="run-S1", item=items[0], dependencies_text=""
    )
    assert "Expected Spec Impact" not in body


def test_field_mapping_uses_repository_ids():
    mapping = {"work": {"intent_and_contract": "contract", "spec_impact": "specs"}}
    assert mapped_field_ids(mapping, "work", "openspec") == {
        "contract", "specs"
    }


def test_none_policy_removes_spec_from_required_ids():
    mapping = {"work": {"intent_and_contract": "contract", "spec_impact": "specs"}}
    assert mapped_field_ids(mapping, "work", "none") == {"contract"}


def test_renderer_uses_mapped_field_labels(tmp_path):
    _, items, _ = load_issue_bundle(bundle_without_impact(tmp_path), spec_mode="none")
    form_path = tmp_path / "form.yml"
    form_path.write_text(yaml.safe_dump({
        "name": "Work", "body": [{
            "type": "textarea", "id": "contract",
            "attributes": {"label": "Repository Contract"}
        }]
    }), encoding="utf-8")
    form = load_issue_form(form_path)
    body = render_sub_issue_body(
        form=form, change_id="run-S1", item=items[0], dependencies_text="",
        field_mapping={"work": {"intent_and_contract": "contract"}},
    )
    assert "## Repository Contract" in body
