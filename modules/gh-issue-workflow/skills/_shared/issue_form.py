#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from issue_bundle import SpecImpact, WorkItem


class IssueFormError(RuntimeError):
    pass


@dataclass(frozen=True)
class IssueFormField:
    id: str
    label: str
    type: str


@dataclass(frozen=True)
class IssueForm:
    path: Path
    name: str
    fields: list[IssueFormField]


def _require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise IssueFormError(f"Expected mapping for {label}, got {value!r}")


def _require_string(value: Any, *, label: str) -> str:
    if isinstance(value, str):
        return value
    raise IssueFormError(f"Expected string for {label}, got {value!r}")


def _as_label(field_id: str, attributes: dict[str, Any]) -> str:
    raw = attributes.get("label")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return field_id


def load_issue_form(path: Path) -> IssueForm:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise IssueFormError("Loading GitHub issue forms requires PyYAML") from exc
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise IssueFormError(f"Failed to read issue form: {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise IssueFormError(f"Invalid YAML issue form: {path}: {exc}") from exc

    root = _require_mapping(payload, label="issue_form")
    name = _require_string(root.get("name", ""), label="issue_form.name").strip() or str(path)
    body = root.get("body", [])
    if not isinstance(body, list):
        raise IssueFormError(f"Expected list for issue_form.body, got {body!r}")

    fields: list[IssueFormField] = []
    seen: set[str] = set()
    for idx, entry in enumerate(body, start=1):
        if not isinstance(entry, dict):
            continue
        entry_type = entry.get("type")
        if entry_type == "markdown":
            continue
        field_id = entry.get("id")
        if not isinstance(field_id, str) or not field_id.strip():
            raise IssueFormError(f"Missing id for issue_form.body[{idx}] in {path}")
        field_id = field_id.strip()
        if field_id in seen:
            raise IssueFormError(f"Duplicate field id {field_id!r} in {path}")
        seen.add(field_id)
        attributes = entry.get("attributes", {})
        attributes = attributes if isinstance(attributes, dict) else {}
        fields.append(
            IssueFormField(
                id=field_id,
                label=_as_label(field_id, attributes),
                type=str(entry_type or ""),
            )
        )

    if not fields:
        raise IssueFormError(f"No fields found in issue form: {path}")

    return IssueForm(path=path, name=name, fields=fields)


def require_field_ids(*, form: IssueForm, required: set[str]) -> None:
    present = {field.id for field in form.fields}
    missing = sorted(required - present)
    if missing:
        raise IssueFormError(f"Issue form {form.path} is missing required field ids: {missing}")


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _optional_bullets(items: list[str]) -> str:
    return "- (none)" if not items else _bullets(items)


def _strip_issue_title_prefix(title: str) -> str:
    trimmed = title.strip()
    for prefix in ("[Sub]", "[Plan]", "[Task]"):
        if trimmed.startswith(prefix):
            return trimmed[len(prefix) :].strip()
    return trimmed


def _render_spec_impact(impact: SpecImpact) -> str:
    paths = [f"- `{path}`" for path in impact.spec_paths] or ["- (none)"]
    return "\n".join([impact.rationale.strip(), "", "Expected canonical specs:", *paths])


def render_sub_issue_body(
    *,
    form: IssueForm,
    change_id: str,
    item: WorkItem,
    dependencies_text: str,
    prefix_lines: list[str] | None = None,
) -> str:
    prefix: list[str] = []
    if prefix_lines:
        prefix.extend([line.rstrip() for line in prefix_lines if line.strip()])
    prefix.extend(
        [
            "<!-- PLAN_ROLE:SUB -->",
            f"<!-- CHANGE_ID:{change_id} -->",
        ]
    )

    labels = {field.id: field.label for field in form.fields}

    change_title = _strip_issue_title_prefix(item.title) or item.id
    deps = dependencies_text.strip() or "(none)"

    sections: list[str] = [
        f"## Change: {change_title}",
        "\n".join(
            [
                f"## {labels.get('intent_and_contract', 'Intent and Contract')}",
                item.intent_and_contract.strip(),
            ]
        ),
        "\n".join(
            [
                f"## {labels.get('owned_atoms', 'Owned Plan Atoms')}",
                _bullets(item.owned_atoms),
            ]
        ),
        "\n".join(
            [
                f"## {labels.get('spec_impact', 'Expected Spec Impact')}",
                _render_spec_impact(item.spec_impact),
            ]
        ),
        "\n".join(
            [
                f"## {labels.get('implementation_plan', 'Implementation Plan')}",
                item.implementation_plan.strip(),
            ]
        ),
        "\n".join(
            [
                f"## {labels.get('file_and_interface_scope', 'File and Interface Scope')}",
                item.file_and_interface_scope.strip(),
            ]
        ),
        "\n".join(
            [
                f"## {labels.get('acceptance_checks', 'Acceptance Checks')}",
                _bullets(item.acceptance_checks),
            ]
        ),
        "\n".join(
            [
                f"## {labels.get('assumptions_defaults', 'Assumptions / Defaults')}",
                item.assumptions_defaults.strip(),
            ]
        ),
        "\n".join(
            [
                f"## {labels.get('references', 'References')}",
                _optional_bullets(item.references),
            ]
        ),
        "\n".join(
            [
                f"## {labels.get('handoff_contract', 'Handoff Contract')}",
                item.handoff_contract.strip(),
            ]
        ),
        "\n".join(
            [
                f"## {labels.get('dependencies', 'Dependencies')}",
                deps,
            ]
        ),
    ]

    prefix_text = "\n".join(prefix).strip()
    sections_text = "\n\n".join(sections).strip()
    if sections_text:
        return f"{prefix_text}\n\n{sections_text}\n"
    return f"{prefix_text}\n"


def render_parent_body(
    *,
    form: IssueForm,
    change_id: str,
    plan_key: str,
    run_id: str,
    objective: str,
    scope: list[str],
    assumptions: list[str],
    atom_registry: list[str],
    coverage_matrix: list[str],
    source_plan_path: str,
    source_plan_sha256: str,
    child_issue_numbers: list[int],
    planned_child_ids: list[str] | None = None,
) -> str:
    prefix = "\n".join(
        [
            "<!-- PLAN_ROLE:PARENT -->",
            f"<!-- CHANGE_ID:{change_id} -->",
            f"<!-- PLAN_KEY:{plan_key} -->",
            f"<!-- PLAN_RUN:{run_id} -->",
        ]
    )

    sections: list[str] = []
    for field in form.fields:
        if field.id == "objective":
            sections.append(f"## {field.label}\n{objective.strip() or '(none)'}")
        elif field.id == "scope":
            scope_text = _bullets(scope) if scope else "- (none)"
            sections.append(f"## {field.label}\n{scope_text}")
        elif field.id == "assumptions":
            assumptions_text = _bullets(assumptions) if assumptions else "- (none)"
            sections.append(f"## {field.label}\n{assumptions_text}")
        elif field.id == "atom_registry":
            atoms_text = _bullets(atom_registry) if atom_registry else "- (none)"
            sections.append(f"## {field.label}\n{atoms_text}")
        elif field.id == "coverage_matrix":
            coverage_text = _bullets(coverage_matrix) if coverage_matrix else "- (none)"
            sections.append(f"## {field.label}\n{coverage_text}")
        else:
            continue

    planned_child_ids = planned_child_ids or []
    if child_issue_numbers:
        sub_issues_text = "\n".join(f"- #{number}" for number in child_issue_numbers)
    elif planned_child_ids:
        sub_issues_text = "\n".join(f"- {item_id} (planned)" for item_id in planned_child_ids)
    else:
        sub_issues_text = "- (none)"
    sections.append(
        "\n".join(
            [
                "## Source",
                f"- plan: `{source_plan_path}`",
                f"- sha256: `{source_plan_sha256}`",
            ]
        )
    )
    sections.append("## Sub-issues\n" + sub_issues_text)

    return "\n\n".join([prefix, *sections]).strip() + "\n"
