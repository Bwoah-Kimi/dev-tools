#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from atom_ids import atom_id_from_line
from issue_bundle import (
    IssueBundleError,
    WorkItem,
    load_issue_bundle,
)

_PLACEHOLDER_PATTERNS = [
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bFIXME\b", re.IGNORECASE),
    re.compile(r"<\s*fill\s*>", re.IGNORECASE),
    re.compile(r"<\s*tbd\s*>", re.IGNORECASE),
]


def _contains_placeholder(text: str) -> bool:
    if not text.strip():
        return False
    if text.strip().lower() in {"(none)", "<fill>", "<tbd>"}:
        return True
    return any(pattern.search(text) is not None for pattern in _PLACEHOLDER_PATTERNS)


def _warn(warnings: list[str], message: str) -> None:
    warnings.append(message)


def _check_required_text(*, warnings: list[str], label: str, value: str, item: WorkItem) -> None:
    if _contains_placeholder(value):
        _warn(
            warnings,
            f"{item.id}: {label} looks like a placeholder ({value.strip()!r})",
        )


def _check_required_text_allow_none(
    *, warnings: list[str], label: str, value: str, item: WorkItem
) -> None:
    if value.strip().lower() == "(none)":
        return
    _check_required_text(warnings=warnings, label=label, value=value, item=item)


def _check_required_list(
    *, warnings: list[str], label: str, values: list[str], item: WorkItem
) -> None:
    for idx, value in enumerate(values, start=1):
        if _contains_placeholder(value):
            message = f"{item.id}: {label}[{idx}] looks like a placeholder ({value.strip()!r})"
            _warn(
                warnings,
                message,
            )


def _is_canonical_spec_path(value: str) -> bool:
    path = PurePosixPath(value)
    return not (
        "\\" in value
        or path.is_absolute()
        or ".." in path.parts
        or len(path.parts) < 4
        or path.parts[:2] != ("openspec", "specs")
        or path.name != "spec.md"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a gh-plan-to-issues JSON bundle before syncing."
    )
    parser.add_argument("--bundle", required=True, type=Path, help="Path to bundle.json")
    args = parser.parse_args()

    try:
        parent, items, _ = load_issue_bundle(args.bundle)
    except IssueBundleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    item_ids = {item.id for item in items}

    atom_ids: list[str] = []
    atom_id_set: set[str] = set()
    for idx, entry in enumerate(parent.atom_registry, start=1):
        atom_id = atom_id_from_line(entry)
        if not atom_id:
            errors.append(f"parent.atom_registry[{idx}] must start with 'A<number>:': {entry!r}")
            continue
        if atom_id in atom_id_set:
            errors.append(f"Duplicate atom id in parent.atom_registry: {atom_id}")
            continue
        atom_ids.append(atom_id)
        atom_id_set.add(atom_id)

    owners_by_atom: dict[str, set[str]] = {atom_id: set() for atom_id in atom_ids}
    spec_path_users: dict[str, list[str]] = {}

    for item in items:
        _check_required_text(
            warnings=warnings,
            label="intent_and_contract",
            value=item.intent_and_contract,
            item=item,
        )
        _check_required_list(
            warnings=warnings,
            label="owned_atoms",
            values=item.owned_atoms,
            item=item,
        )
        _check_required_text(
            warnings=warnings,
            label="implementation_plan",
            value=item.implementation_plan,
            item=item,
        )
        _check_required_text(
            warnings=warnings,
            label="file_and_interface_scope",
            value=item.file_and_interface_scope,
            item=item,
        )
        _check_required_list(
            warnings=warnings,
            label="acceptance_checks",
            values=item.acceptance_checks,
            item=item,
        )
        _check_required_text_allow_none(
            warnings=warnings,
            label="assumptions_defaults",
            value=item.assumptions_defaults,
            item=item,
        )
        _check_required_text_allow_none(
            warnings=warnings,
            label="handoff_contract",
            value=item.handoff_contract,
            item=item,
        )

        for token in item.dependencies:
            normalized = token.strip()
            if not normalized or normalized.lower() == "(none)":
                message = (
                    f"{item.id}: dependencies contains {token!r}; prefer an empty list instead"
                )
                _warn(
                    warnings,
                    message,
                )
                continue
            if normalized.startswith("#") and normalized[1:].isdigit():
                continue
            if normalized in item_ids:
                continue
            _warn(
                warnings,
                f"{item.id}: dependencies token {normalized!r} is not '#<number>' "
                "and not another items[].id",
            )

        for ref in item.references:
            if ref.strip().lower() == "(none)":
                _warn(
                    warnings,
                    f"{item.id}: references contains '(none)'; prefer an empty list",
                )

        for raw_owned in item.owned_atoms:
            atom_id = atom_id_from_line(raw_owned)
            if not atom_id:
                errors.append(
                    f"{item.id}: owned_atoms entry must start with 'A<number>:': {raw_owned!r}"
                )
                continue
            if atom_id not in atom_id_set:
                errors.append(
                    f"{item.id}: owned atom {atom_id} is not present in parent.atom_registry"
                )
                continue
            owners_by_atom.setdefault(atom_id, set()).add(item.id)

        _check_required_text(
            warnings=warnings,
            label="spec_impact.rationale",
            value=item.spec_impact.rationale,
            item=item,
        )
        seen_spec_paths: set[str] = set()
        for idx, spec_path in enumerate(item.spec_impact.spec_paths, start=1):
            label = f"{item.id}: spec_impact.spec_paths[{idx}]"
            if not _is_canonical_spec_path(spec_path):
                errors.append(
                    f"{label} must be a canonical openspec/specs/**/spec.md path: {spec_path!r}"
                )
                continue
            if spec_path in seen_spec_paths:
                errors.append(f"{label} duplicates {spec_path!r} within {item.id}")
                continue
            seen_spec_paths.add(spec_path)
            spec_path_users.setdefault(spec_path, []).append(item.id)

        for idx, check in enumerate(item.acceptance_checks, start=1):
            referenced = sorted(set(re.findall(r"\bA\d+\b", check)))
            if not referenced:
                errors.append(
                    f"{item.id}: acceptance_checks[{idx}] must reference at least "
                    f"one atom id (e.g. '[A3]'): {check!r}"
                )
                continue
            unknown = [atom for atom in referenced if atom not in atom_id_set]
            if unknown:
                errors.append(
                    f"{item.id}: acceptance_checks[{idx}] references unknown atoms: "
                    f"{', '.join(unknown)}"
                )

    unowned = [atom_id for atom_id in atom_ids if not owners_by_atom.get(atom_id)]
    if unowned:
        errors.append(
            "Unowned atoms in parent.atom_registry "
            "(every atom must be owned by at least one item): " + ", ".join(unowned)
        )

    for spec_path, users in sorted(spec_path_users.items()):
        unique_users = sorted(set(users))
        if len(unique_users) > 1:
            _warn(
                warnings,
                f"Expected spec path {spec_path!r} is shared by Tasks "
                f"{', '.join(unique_users)}; bundle review must verify that their "
                "contracts do not conflict and encode an ordering dependency if needed",
            )

    if errors:
        print(f"ERROR: Bundle invalid: {args.bundle}", file=sys.stderr)
        for message in errors:
            print(f"- {message}", file=sys.stderr)
        return 1

    print(f"Bundle OK: {args.bundle}")
    print(f"- atoms: {len(atom_ids)}")
    print(f"- items: {len(items)}")
    for item in items:
        print(f"- {item.id}: {item.title} ({len(item.spec_impact.spec_paths)} expected spec paths)")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
