#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from gh_cli import GhCliError
from gh_context import resolve_context
from gh_issue_blocking import reconcile_blocked_by
from gh_issues import (
    GitHubIssueClient,
    GitHubIssueError,
    IssueSummary,
)
from gh_repo import require_issue_type_id
from issue_bundle import (
    IssueBundleError,
    WorkItem,
    bundle_sha256,
    load_issue_bundle,
    render_mapping_table,
    resolve_dependency_refs,
)
from issue_form import (
    IssueFormError,
    load_issue_form,
    mapped_field_ids,
    render_sub_issue_body,
    require_field_ids,
)
from json_io import JsonIOError, load_json, write_json
from paths import sanitize_component


class SyncError(RuntimeError):
    pass


REQUIRED_SUB_ISSUE_FORM_IDS = {
    "intent_and_contract",
    "owned_atoms",
    "spec_impact",
    "implementation_plan",
    "file_and_interface_scope",
    "acceptance_checks",
    "assumptions_defaults",
    "references",
    "handoff_contract",
    "dependencies",
}
DEFAULT_FIELD_MAPPING = {
    "work": {field: field for field in REQUIRED_SUB_ISSUE_FORM_IDS}
}


@dataclass
class SyncedItem:
    item: WorkItem
    change_id: str
    summary: IssueSummary


def _validate_unique_change_ids(*, items: list[WorkItem]) -> None:
    seen_issue_suffixes: dict[str, str] = {}
    for item in items:
        issue_suffix = sanitize_component(item.id)
        existing = seen_issue_suffixes.get(issue_suffix)
        if existing is not None:
            raise SyncError(
                "Sub-issue CHANGE_ID collision after sanitization: "
                f"{existing!r} and {item.id!r} both map to {issue_suffix!r}. "
                "Use distinct items[].id tokens."
            )
        seen_issue_suffixes[issue_suffix] = item.id


def _infer_plan_key_and_run_id(bundle_path: Path) -> tuple[str, str]:
    parts = list(bundle_path.resolve().parts)
    for idx, part in enumerate(parts):
        if part != "runs":
            continue
        if idx == 0 or idx + 1 >= len(parts):
            continue
        plan_key = parts[idx - 1]
        run_id = parts[idx + 1]
        if plan_key and run_id:
            return plan_key, run_id
    return "", ""


def _load_sync_state(path: Path) -> dict[str, Any]:
    try:
        return load_json(path)
    except JsonIOError as exc:
        raise SyncError(f"Invalid sync state file: {path}") from exc


def _write_sync_state(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def _state_items_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        return {}
    by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        item_id = raw.get("id")
        if isinstance(item_id, str) and item_id:
            by_id[item_id] = raw
    return by_id


def _render_prefix_lines(*, plan_key: str, run_id: str, item_id: str) -> list[str]:
    return [
        f"<!-- PLAN_KEY:{plan_key} -->",
        f"<!-- PLAN_RUN:{run_id} -->",
        f"<!-- PLAN_ITEM:{item_id} -->",
    ]


def _sync_items(
    *,
    items: list[WorkItem],
    form: Any,
    issue_client: GitHubIssueClient,
    task_issue_type_id: str,
    effective_plan_key: str,
    effective_run_id: str,
    existing_items: dict[str, dict[str, Any]],
    state: dict[str, Any],
    sync_state_path: Path | None,
    field_mapping: dict | None,
) -> list[SyncedItem]:
    synced: list[SyncedItem] = []
    for item in items:
        change_id = f"{effective_plan_key}-{effective_run_id}-{sanitize_component(item.id)}"
        existing = existing_items.get(item.id, {})
        issue_number = existing.get("issue_number")
        summary: IssueSummary | None = None
        if isinstance(issue_number, int) and issue_number > 0:
            summary = issue_client.get_issue(issue_number)
        if summary is None:
            body = render_sub_issue_body(
                form=form,
                change_id=change_id,
                item=item,
                dependencies_text=" ".join(item.dependencies),
                prefix_lines=_render_prefix_lines(
                    plan_key=effective_plan_key,
                    run_id=effective_run_id,
                    item_id=item.id,
                ),
                field_mapping=field_mapping,
            )
            summary = issue_client.create_issue(item.title, body)
            if sync_state_path:
                state_items = _state_items_by_id(state)
                state_items[item.id] = {
                    "id": item.id,
                    "change_id": change_id,
                    "issue_number": summary.number,
                    "url": summary.url,
                }
                state["items"] = list(state_items.values())
                _write_sync_state(sync_state_path, state)

        GitHubIssueClient.set_issue_type(
            issue_id=summary.id,
            issue_type_id=task_issue_type_id,
        )
        synced.append(SyncedItem(item=item, change_id=change_id, summary=summary))
    return synced


def _reconcile_dependencies(
    *,
    synced: list[SyncedItem],
    form: Any,
    issue_client: GitHubIssueClient,
    effective_plan_key: str,
    effective_run_id: str,
    field_mapping: dict | None,
) -> None:
    id_to_issue = {row.item.id: row.summary.number for row in synced}
    id_by_issue_number = {row.summary.number: row.summary.id for row in synced}
    dep_id_cache: dict[int, str] = {}

    for row in synced:
        dep_value, unresolved = resolve_dependency_refs(row.item.dependencies, id_to_issue)
        if unresolved:
            raise SyncError(
                f"Unresolved dependency tokens for {row.item.id!r}: "
                + ", ".join(sorted(set(unresolved)))
            )

        updated_body = render_sub_issue_body(
            form=form,
            change_id=row.change_id,
            item=row.item,
            dependencies_text=dep_value,
            prefix_lines=_render_prefix_lines(
                plan_key=effective_plan_key,
                run_id=effective_run_id,
                item_id=row.item.id,
            ),
            field_mapping=field_mapping,
        )
        row.summary = issue_client.edit_issue(row.summary.number, row.item.title, updated_body)
        dep_numbers = [
            int(token[1:])
            for token in dep_value.split()
            if token.startswith("#") and token[1:].isdigit()
        ]
        desired_ids: set[str] = set()
        for dep_number in dep_numbers:
            dep_id = id_by_issue_number.get(dep_number) or dep_id_cache.get(dep_number)
            if not dep_id:
                dep_id = issue_client.get_issue(dep_number).id
                dep_id_cache[dep_number] = dep_id
            desired_ids.add(dep_id)
        reconcile_blocked_by(issue_id=row.summary.id, desired_blocker_ids=desired_ids)


def sync_bundle(
    *,
    bundle_path: Path,
    repo: str,
    repo_owner: str,
    repo_name: str,
    issue_template: Path,
    plan_key: str | None,
    run_id: str | None,
    sync_state_path: Path | None,
    dry_run: bool,
    spec_mode: str = "openspec",
    field_mapping: dict | None = None,
    work_issue_type: str = "Task",
) -> dict[str, Any]:
    if not bundle_path.exists():
        raise SyncError(f"Bundle file not found: {bundle_path}")
    effective_mapping = field_mapping if field_mapping is not None else DEFAULT_FIELD_MAPPING
    if not issue_template.exists():
        raise SyncError(f"Issue template not found: {issue_template}")

    _, items, raw_payload = load_issue_bundle(bundle_path, spec_mode=spec_mode)
    bundle_sha = bundle_sha256(raw_payload)
    _validate_unique_change_ids(items=items)

    inferred_plan_key, inferred_run_id = _infer_plan_key_and_run_id(bundle_path)
    effective_plan_key = sanitize_component(plan_key or inferred_plan_key)
    effective_run_id = sanitize_component(run_id or inferred_run_id)
    if not effective_plan_key or effective_plan_key == "x":
        raise SyncError(
            "Missing plan_key. Place bundle at "
            "out/gh-plan-to-issues/<plan_key>/runs/<run_id>/bundle.json."
        )
    if not effective_run_id or effective_run_id == "x":
        raise SyncError(
            "Missing run_id. Provide --run-id or place bundle at "
            "out/gh-plan-to-issues/<plan_key>/runs/<run_id>/bundle.json."
        )

    try:
        form = load_issue_form(issue_template)
        require_field_ids(
            form=form,
            required=mapped_field_ids(effective_mapping, "work", spec_mode),
        )
    except IssueFormError as exc:
        raise SyncError(str(exc)) from exc

    if dry_run:
        preview: list[dict[str, Any]] = []
        for item in items:
            change_id = f"{effective_plan_key}-{effective_run_id}-{sanitize_component(item.id)}"
            body = render_sub_issue_body(
                form=form,
                change_id=change_id,
                item=item,
                dependencies_text=" ".join(item.dependencies),
                prefix_lines=_render_prefix_lines(
                    plan_key=effective_plan_key,
                    run_id=effective_run_id,
                    item_id=item.id,
                ),
                field_mapping=effective_mapping,
            )
            preview.append(
                {
                    "id": item.id,
                    "change_id": change_id,
                    "title": item.title,
                    "dependencies": list(item.dependencies),
                    "body": body,
                    "body_preview": body.splitlines()[:12],
                }
            )
        return {
            "bundle": str(bundle_path),
            "plan_key": effective_plan_key,
            "run_id": effective_run_id,
            "bundle_sha256": bundle_sha,
            "repo": repo,
            "dry_run": True,
            "items": preview,
        }

    state: dict[str, Any] = _load_sync_state(sync_state_path) if sync_state_path else {}
    if state.get("bundle_sha256") and state.get("bundle_sha256") != bundle_sha:
        raise SyncError(
            "Sync state bundle hash mismatch: "
            f"{state.get('bundle_sha256')} vs {bundle_sha}. "
            f"Refusing to continue with {sync_state_path}."
        )

    issue_client = GitHubIssueClient(repo)
    task_issue_type_id = require_issue_type_id(
        owner=repo_owner,
        name=repo_name,
        issue_type_name=work_issue_type,
    )

    if sync_state_path:
        state.setdefault("plan_key", effective_plan_key)
        state.setdefault("run_id", effective_run_id)
        state.setdefault("bundle_sha256", bundle_sha)
        state.setdefault("repo", repo)
        state.setdefault("items", [])
        state.setdefault("status", "partial")
        _write_sync_state(sync_state_path, state)

    existing_items = _state_items_by_id(state)

    synced = _sync_items(
        items=items,
        form=form,
        issue_client=issue_client,
        task_issue_type_id=task_issue_type_id,
        effective_plan_key=effective_plan_key,
        effective_run_id=effective_run_id,
        existing_items=existing_items,
        state=state,
        sync_state_path=sync_state_path,
        field_mapping=effective_mapping,
    )

    _reconcile_dependencies(
        synced=synced,
        form=form,
        issue_client=issue_client,
        effective_plan_key=effective_plan_key,
        effective_run_id=effective_run_id,
        field_mapping=effective_mapping,
    )

    result: dict[str, Any] = {
        "bundle": str(bundle_path),
        "plan_key": effective_plan_key,
        "run_id": effective_run_id,
        "bundle_sha256": bundle_sha,
        "repo": repo,
        "items": [
            {
                "id": row.item.id,
                "change_id": row.change_id,
                "issue_id": row.summary.id,
                "issue_number": row.summary.number,
                "url": row.summary.url,
            }
            for row in synced
        ],
        "status": "complete",
    }

    if sync_state_path:
        state.update(result)
        _write_sync_state(sync_state_path, state)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync a JSON issue bundle into GitHub issues.")
    parser.add_argument(
        "--bundle",
        required=True,
        type=Path,
        help="Path to JSON bundle.",
    )
    parser.add_argument("--repo", default=None, help="GitHub repository (OWNER/REPO).")
    parser.add_argument(
        "--issue-template",
        type=Path,
        default=Path(".github/ISSUE_TEMPLATE/sub_issue.yml"),
        help="GitHub issue form YAML template path.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run id used to generate change_id markers (defaults to inferred).",
    )
    parser.add_argument(
        "--sync-state",
        type=Path,
        default=None,
        help="Optional path to persist incremental sync state (resume-safe).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render only; do not call GitHub mutation commands.",
    )
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format.",
    )
    args = parser.parse_args()
    context = resolve_context(repo=args.repo)

    try:
        result = sync_bundle(
            bundle_path=args.bundle,
            repo=context.repo,
            repo_owner=context.repo_owner,
            repo_name=context.repo_name,
            issue_template=args.issue_template,
            plan_key=None,
            run_id=args.run_id,
            sync_state_path=args.sync_state,
            dry_run=args.dry_run,
        )
    except (SyncError, GhCliError, GitHubIssueError, IssueBundleError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if result.get("dry_run"):
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    table_rows = [
        (row["change_id"], row["issue_number"], row["url"])
        for row in result.get("items", [])
        if isinstance(row, dict)
    ]
    print(render_mapping_table(table_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
