#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class IssueBundleError(RuntimeError):
    pass


@dataclass(frozen=True)
class BundleParent:
    title: str
    objective: str
    scope: list[str]
    assumptions: list[str]
    atom_registry: list[str]


@dataclass(frozen=True)
class SpecImpact:
    rationale: str
    spec_paths: list[str]


@dataclass(frozen=True)
class WorkItem:
    id: str
    title: str
    intent_and_contract: str
    owned_atoms: list[str]
    spec_impact: SpecImpact
    implementation_plan: str
    file_and_interface_scope: str
    acceptance_checks: list[str]
    assumptions_defaults: str
    references: list[str]
    handoff_contract: str
    dependencies: list[str]


def _normalize_token(token: str) -> str:
    cleaned = token.strip()
    cleaned = cleaned.rstrip(".,;").strip()
    cleaned = cleaned.strip("`").strip()
    return cleaned.rstrip(".,;")


def _require_str(value: Any, *, label: str) -> str:
    if isinstance(value, str):
        return value
    raise IssueBundleError(f"Expected string for {label}, got {value!r}")


def _require_nonempty_str(value: Any, *, label: str) -> str:
    result = _require_str(value, label=label).strip()
    if not result:
        raise IssueBundleError(f"{label} must be non-empty.")
    return result


def _require_str_list(value: Any, *, label: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise IssueBundleError(f"Expected list for {label}, got {value!r}")
    result: list[str] = []
    for idx, item in enumerate(value, start=1):
        if not isinstance(item, str):
            raise IssueBundleError(f"Expected string for {label}[{idx}], got {item!r}")
        normalized = item.strip()
        if normalized:
            result.append(normalized)
    if not allow_empty and not result:
        raise IssueBundleError(f"{label} must be a non-empty list of strings")
    return result


def _require_object(value: Any, *, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise IssueBundleError(f"Expected object for {label}, got {value!r}")


def _parse_parent(payload: dict[str, Any]) -> BundleParent:
    raw_parent = _require_object(payload.get("parent"), label="parent")
    title = _require_nonempty_str(raw_parent.get("title"), label="parent.title")
    objective = _require_nonempty_str(raw_parent.get("objective"), label="parent.objective")
    scope = _require_str_list(raw_parent.get("scope", []), label="parent.scope", allow_empty=True)
    assumptions = _require_str_list(
        raw_parent.get("assumptions", []),
        label="parent.assumptions",
        allow_empty=True,
    )
    atom_registry = _require_str_list(
        raw_parent.get("atom_registry", []),
        label="parent.atom_registry",
        allow_empty=False,
    )
    return BundleParent(
        title=title,
        objective=objective,
        scope=scope,
        assumptions=assumptions,
        atom_registry=atom_registry,
    )


def _parse_spec_impact(value: Any, *, label: str) -> SpecImpact:
    raw_impact = _require_object(value, label=label)
    rationale = _require_nonempty_str(raw_impact.get("rationale"), label=f"{label}.rationale")
    spec_paths = _require_str_list(
        raw_impact.get("spec_paths"),
        label=f"{label}.spec_paths",
        allow_empty=True,
    )
    return SpecImpact(rationale=rationale, spec_paths=spec_paths)


def load_issue_bundle(
    path: Path,
) -> tuple[BundleParent, list[WorkItem], dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise IssueBundleError(f"Failed to read bundle: {path}") from exc
    except json.JSONDecodeError as exc:
        raise IssueBundleError(f"Invalid JSON bundle: {path}") from exc

    if not isinstance(payload, dict):
        raise IssueBundleError("Issue bundle must be a JSON object.")

    parent = _parse_parent(payload)

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise IssueBundleError("Issue bundle requires a non-empty 'items' list.")

    items: list[WorkItem] = []
    seen_ids: set[str] = set()
    for idx, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            raise IssueBundleError(f"items[{idx}] must be a JSON object.")
        item_id = _normalize_token(_require_str(raw_item.get("id"), label=f"items[{idx}].id"))
        if not item_id:
            raise IssueBundleError(f"items[{idx}].id must be non-empty.")
        if item_id in seen_ids:
            raise IssueBundleError(f"Duplicate item id: {item_id!r}")
        seen_ids.add(item_id)

        title = _require_nonempty_str(raw_item.get("title"), label=f"items[{idx}].title")
        intent_and_contract = _require_nonempty_str(
            raw_item.get("intent_and_contract"),
            label=f"items[{idx}].intent_and_contract",
        )

        owned_atoms = _require_str_list(
            raw_item.get("owned_atoms"),
            label=f"items[{idx}].owned_atoms",
        )

        spec_impact = _parse_spec_impact(
            raw_item.get("spec_impact"),
            label=f"items[{idx}].spec_impact",
        )

        implementation_plan = _require_nonempty_str(
            raw_item.get("implementation_plan"),
            label=f"items[{idx}].implementation_plan",
        )

        file_and_interface_scope = _require_nonempty_str(
            raw_item.get("file_and_interface_scope"),
            label=f"items[{idx}].file_and_interface_scope",
        )

        acceptance_checks = _require_str_list(
            raw_item.get("acceptance_checks"),
            label=f"items[{idx}].acceptance_checks",
        )

        assumptions_defaults = (
            _require_str(
                raw_item.get("assumptions_defaults", "(none)"),
                label=f"items[{idx}].assumptions_defaults",
            ).strip()
            or "(none)"
        )

        references = _require_str_list(
            raw_item.get("references", []),
            label=f"items[{idx}].references",
            allow_empty=True,
        )

        handoff_contract = (
            _require_str(
                raw_item.get("handoff_contract", "(none)"),
                label=f"items[{idx}].handoff_contract",
            ).strip()
            or "(none)"
        )

        dependencies = _require_str_list(
            raw_item.get("dependencies", []),
            label=f"items[{idx}].dependencies",
            allow_empty=True,
        )

        items.append(
            WorkItem(
                id=item_id,
                title=title,
                intent_and_contract=intent_and_contract,
                owned_atoms=owned_atoms,
                spec_impact=spec_impact,
                implementation_plan=implementation_plan,
                file_and_interface_scope=file_and_interface_scope,
                acceptance_checks=acceptance_checks,
                assumptions_defaults=assumptions_defaults,
                references=references,
                handoff_contract=handoff_contract,
                dependencies=dependencies,
            )
        )

    return parent, items, payload


def _canonical_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical_value(item) for key, item in value.items()}
    return value


def canonicalize_bundle_for_hash(payload: dict[str, Any]) -> dict[str, Any]:
    canonical = _canonical_value(payload)
    if not isinstance(canonical, dict):
        return {}
    items = canonical.get("items")
    if isinstance(items, list):
        items.sort(key=lambda item: str(item.get("id", "")))
    return canonical


def bundle_sha256(payload: dict[str, Any]) -> str:
    canonical = canonicalize_bundle_for_hash(payload)
    text = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_dependency_refs(
    dependencies: list[str], id_to_issue: dict[str, int]
) -> tuple[str, list[str]]:
    resolved: list[str] = []
    unresolved: list[str] = []
    for raw in dependencies:
        token = _normalize_token(raw)
        if not token:
            continue
        if token.startswith("#") and token[1:].isdigit():
            resolved.append(token)
        elif token in id_to_issue:
            resolved.append(f"#{id_to_issue[token]}")
        else:
            unresolved.append(token)
    return " ".join(resolved), unresolved


def render_mapping_table(rows: list[tuple[str, int, str]]) -> str:
    header = "| sync_id | issue | url |"
    divider = "|---|---:|---|"
    body = [f"| `{sync_id}` | #{number} | {url} |" for sync_id, number, url in rows]
    return "\n".join([header, divider, *body])
