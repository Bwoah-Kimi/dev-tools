#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from atom_ids import atom_id_from_line  # noqa: E402
from approval import ApprovalError, load_approved_bundle  # noqa: E402
from file_archive import (  # noqa: E402
    FileArchiveError,
    archive_file,
    sha256_file,
)
from gh_cli import GhCliError  # noqa: E402
from gh_context import resolve_context  # noqa: E402
from gh_issues import GitHubIssueClient, GitHubIssueError  # noqa: E402
from gh_repo import require_issue_type_id  # noqa: E402
from gh_subissues import (  # noqa: E402
    add_sub_issue,
    issue_rest_id,
    list_sub_issues,
    remove_sub_issue,
)
from gh_sync_issues import SyncError, sync_bundle  # noqa: E402
from issue_bundle import (  # noqa: E402
    IssueBundleError,
    bundle_sha256,
    load_issue_bundle,
    render_mapping_table,
)
from issue_form import (  # noqa: E402
    IssueForm,
    IssueFormError,
    load_issue_form,
    mapped_field_ids,
    render_parent_body,
    require_field_ids,
)
from json_io import JsonIOError, load_json, write_json  # noqa: E402
from paths import SETUP_HINT, sanitize_component  # noqa: E402
from workflow_config import ConfigError, load_config  # noqa: E402


class PlanSyncError(RuntimeError):
    pass


OUT_ROOT = Path("out/gh-plan-to-issues")
STATE_FILENAME = "state.json"
PARENT_CHANGE_ID_PREFIX = "parent"

REQUIRED_PARENT_FORM_IDS = {
    "objective",
    "scope",
    "assumptions",
    "atom_registry",
    "coverage_matrix",
}


def _build_coverage_matrix(
    *,
    atom_registry: list[str],
    items: list[Any],
    owner_by_item_id: dict[str, str],
) -> list[str]:
    atom_ids: list[str] = []
    seen_atoms: set[str] = set()
    for idx, entry in enumerate(atom_registry, start=1):
        atom_id = atom_id_from_line(entry)
        if not atom_id:
            raise PlanSyncError(
                "Invalid atom_registry entry (expected 'A<number>:' prefix): "
                f"atom_registry[{idx}]={entry!r}"
            )
        if atom_id in seen_atoms:
            raise PlanSyncError(f"Duplicate atom id in atom_registry: {atom_id}")
        seen_atoms.add(atom_id)
        atom_ids.append(atom_id)

    owners_by_atom: dict[str, list[str]] = {atom_id: [] for atom_id in atom_ids}
    unknown_atoms: set[str] = set()

    for item in items:
        item_id = getattr(item, "id", "")
        owner = owner_by_item_id.get(str(item_id), "")
        for raw in getattr(item, "owned_atoms", []):
            atom_id = atom_id_from_line(str(raw))
            if not atom_id:
                raise PlanSyncError(
                    f"Invalid owned_atoms entry for {item_id!r} "
                    f"(expected 'A<number>:' prefix): {raw!r}"
                )
            if atom_id not in owners_by_atom:
                unknown_atoms.add(atom_id)
                continue
            if owner and owner not in owners_by_atom[atom_id]:
                owners_by_atom[atom_id].append(owner)

    if unknown_atoms:
        raise PlanSyncError(
            "Items reference atoms not present in parent.atom_registry: "
            + ", ".join(sorted(unknown_atoms))
        )

    unowned = [atom_id for atom_id, owners in owners_by_atom.items() if not owners]
    if unowned:
        raise PlanSyncError(
            "Atom registry contains unowned atoms "
            "(every atom must be owned by at least one sub-issue): "
            + ", ".join(unowned)
        )

    return [f"{atom_id} -> {' '.join(owners_by_atom[atom_id])}" for atom_id in atom_ids]


def _ensure_parent_issue(
    *,
    issue_client: GitHubIssueClient,
    feature_issue_type_id: str,
    parent_form: IssueForm,
    plan_key: str,
    run_id: str,
    parent_title: str,
    parent_objective: str,
    parent_scope: list[str],
    parent_assumptions: list[str],
    parent_atom_registry: list[str],
    parent_coverage_matrix: list[str],
    source_plan_path: str,
    source_plan_sha256: str,
    child_issue_numbers: list[int],
    field_mapping: dict | None = None,
) -> dict[str, Any]:
    parent_change_id = f"{PARENT_CHANGE_ID_PREFIX}-{plan_key}"
    body = render_parent_body(
        form=parent_form,
        change_id=parent_change_id,
        plan_key=plan_key,
        run_id=run_id,
        objective=parent_objective,
        scope=parent_scope,
        assumptions=parent_assumptions,
        atom_registry=parent_atom_registry,
        coverage_matrix=parent_coverage_matrix,
        source_plan_path=source_plan_path,
        source_plan_sha256=source_plan_sha256,
        child_issue_numbers=child_issue_numbers,
        field_mapping=field_mapping,
    )
    summary = issue_client.upsert_by_change_id(
        change_id=parent_change_id,
        title=parent_title,
        body=body,
        upsert=True,
    )
    try:
        GitHubIssueClient.set_issue_type(
            issue_id=summary.id,
            issue_type_id=feature_issue_type_id,
        )
    except GitHubIssueError as exc:
        raise PlanSyncError(f"Failed to set parent issue type: {exc}") from exc
    return {"issue_number": summary.number, "url": summary.url, "issue_id": summary.id}


def _reconcile_sub_issues(
    *,
    repo: str,
    parent_number: int,
    desired_child_numbers: list[int],
) -> None:
    desired = {num for num in desired_child_numbers if isinstance(num, int)}
    existing = list_sub_issues(repo=repo, parent_number=parent_number)
    existing_by_number: dict[int, int] = {}
    for item in existing:
        number = item.get("number")
        sub_id = item.get("id")
        if isinstance(number, int) and isinstance(sub_id, int):
            existing_by_number[number] = sub_id

    for number, sub_id in existing_by_number.items():
        if number in desired:
            continue
        remove_sub_issue(
            repo=repo,
            parent_number=parent_number,
            sub_issue_id=sub_id,
        )

    for number in sorted(desired):
        if number in existing_by_number:
            continue
        sub_id = issue_rest_id(repo=repo, issue_number=number)
        add_sub_issue(
            repo=repo,
            parent_number=parent_number,
            sub_issue_id=sub_id,
        )


def _owner_map(sync_items: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(item.get("id")): f"#{item.get('issue_number')}"
        for item in sync_items
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("issue_number"), int)
    }


def _child_numbers(sync_items: list[dict[str, Any]]) -> list[int]:
    return [
        int(item["issue_number"])
        for item in sync_items
        if isinstance(item, dict) and isinstance(item.get("issue_number"), int)
    ]


def _relative_to_plan_dir(plan_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(plan_dir))
    except ValueError:
        return str(path)


def _sync_paths(plan_dir: Path, run_id: str) -> tuple[Path, Path]:
    run_dir = plan_dir / "runs" / run_id
    return run_dir / "bundle.json", run_dir / "sync.json"


def _close_and_remove_old_run(
    *,
    old_sync: dict[str, Any],
    new_sync: dict[str, Any],
    repo: str,
) -> None:
    old_items = old_sync.get("items", [])
    if not isinstance(old_items, list) or not old_items:
        return

    new_numbers = [
        f"#{item.get('issue_number')}"
        for item in new_sync.get("items", [])
        if isinstance(item, dict) and isinstance(item.get("issue_number"), int)
    ]
    plan_key = new_sync.get("plan_key", "")
    run_id = new_sync.get("run_id", "")
    comment_prefix = f"Superseded by plan '{plan_key}' run {run_id}."
    comment_suffix = (
        "New issues: " + " ".join(new_numbers) if new_numbers else "New issues created."
    )
    comment = f"{comment_prefix} {comment_suffix}".strip()

    issue_client = GitHubIssueClient(repo)

    for raw in old_items:
        if not isinstance(raw, dict):
            continue
        issue_number = raw.get("issue_number")
        if not isinstance(issue_number, int):
            continue

        try:
            summary = issue_client.get_issue(issue_number)
        except GitHubIssueError:
            summary = None
        if summary is not None and summary.state != "CLOSED":
            issue_client.close_issue(
                issue_number, comment=comment, reason="not planned"
            )


def _safe_load_json(path: Path) -> dict[str, Any]:
    try:
        return load_json(path)
    except JsonIOError as exc:
        raise PlanSyncError(str(exc)) from exc


def _parse_args() -> argparse.Namespace:
    epilog = "\n".join([
        "Sync behavior:",
        "  - archives runs under out/gh-plan-to-issues/<plan_key>/runs/<run_id>/",
        "  - snapshots the source plan under "
        "out/gh-plan-to-issues/<plan_key>/runs/<run_id>/plan.md",
        "  - creates/updates the parent issue (Issue Type = Feature)",
        "  - creates/updates sub-issues (Issue Type = Task)",
        "  - links sub-issues under the parent issue",
        "  - closes the previous active run's issues for that plan_key",
        "  - reconciles dependencies using GitHub-native Blocked by links (items[].dependencies)",
        "Use --force-new-run to rotate even when the bundle is unchanged.",
        "",
        SETUP_HINT,
    ])
    parser = argparse.ArgumentParser(
        description=(
            "Rerun-aware plan folder sync: archive runs, replace old issues, and "
            "sync a new bundle."
        ),
        epilog=epilog,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--plan", required=True, type=Path, help="Path to the plan file."
    )
    parser.add_argument(
        "--bundle", required=True, type=Path, help="Path to JSON bundle."
    )
    parser.add_argument("--repo", default=None, help="GitHub repository (OWNER/REPO).")
    parser.add_argument(
        "--issue-template",
        type=Path,
        default=None,
        help="GitHub issue form YAML template path for work issues.",
    )
    parser.add_argument(
        "--parent-template",
        type=Path,
        default=None,
        help="GitHub issue form YAML template path for parent issues.",
    )
    parser.add_argument("--config", type=Path, default=None, help="Repository workflow config.")
    parser.add_argument(
        "--spec-mode", choices=("openspec", "optional", "none"), default=None
    )
    parser.add_argument("--spec-root", action="append", default=[])
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument(
        "--force-new-run",
        action="store_true",
        help=(
            "Always create a new run (and replace the previous active run) even "
            "when the bundle is unchanged."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only; do not create/close issues or write local state.",
    )
    parser.add_argument(
        "--approved-bundle",
        type=Path,
        default=None,
        help="Reviewed approval metadata; required for a live sync.",
    )
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format.",
    )
    return parser.parse_args()


def _workflow_config(args: argparse.Namespace):
    overrides: dict[str, Any] = {}
    if args.spec_mode:
        overrides["spec_policy"] = {"mode": args.spec_mode}
    if args.spec_root:
        overrides.setdefault("spec_policy", {})["roots"] = args.spec_root
    return load_config(Path.cwd(), overrides, config_path=args.config)


def _prepare_run(args: argparse.Namespace, *, persist: bool) -> tuple[
    Any,  # context
    str,  # plan_key
    Path,  # plan_dir
    str,  # run_id
    str,  # plan_sha
    str,  # bundle_hash
    Path,  # bundle_out_path
    Path,  # sync_out_path
    Any,  # parent (from bundle)
    list[Any],  # items (from bundle)
    GitHubIssueClient,
    str,  # feature_issue_type_id
    IssueForm,  # parent_form
]:
    try:
        config = _workflow_config(args)
        args.workflow_config = config
        args.spec_mode = config.spec_mode
        args.issue_template = args.issue_template or config.template_path("work")
        args.parent_template = args.parent_template or config.template_path("parent")
        context = resolve_context(
            repo=args.repo,
            repo_root=config.repo_root,
            context_path=config.output_path("cache") / "context.json",
            write_cache=persist,
        )
    except (ConfigError, GhCliError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(SETUP_HINT, file=sys.stderr)
        raise SystemExit(1) from exc

    if not args.plan.exists():
        print(f"ERROR: plan file not found: {args.plan}", file=sys.stderr)
        raise SystemExit(1)
    if not args.bundle.exists():
        print(f"ERROR: bundle file not found: {args.bundle}", file=sys.stderr)
        raise SystemExit(1)

    plan_key = sanitize_component(args.plan.stem)
    if plan_key == "x":
        print("ERROR: could not derive a valid plan_key", file=sys.stderr)
        raise SystemExit(1)

    output_root = args.output_root or config.output_path("plan")
    if not output_root.is_absolute():
        output_root = config.repo_root / output_root
    plan_dir = output_root / plan_key

    bundle_payload = _safe_load_json(args.bundle)

    try:
        plan_sha = sha256_file(args.plan)
    except OSError as exc:
        print(f"ERROR: failed to read plan file: {args.plan}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        bundle_hash = bundle_sha256(bundle_payload)
    except Exception as exc:
        print(f"ERROR: failed to hash bundle: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    base_run_id = bundle_hash[:8]
    run_id = f"{base_run_id}-{int(time.time())}" if args.force_new_run else base_run_id

    bundle_out_path, sync_out_path = _sync_paths(plan_dir, run_id)
    run_dir = bundle_out_path.parent

    if persist:
        try:
            archive_file(
                source_path=args.plan,
                dest_path=run_dir / "plan.md",
                expected_sha256=plan_sha,
            )
        except (OSError, FileArchiveError) as exc:
            print(
                f"ERROR: failed to archive plan file to {run_dir / 'plan.md'}: {exc}",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc

        source_plan = bundle_payload.get("source_plan")
        if not isinstance(source_plan, dict):
            source_plan = {}
            bundle_payload["source_plan"] = source_plan
        source_plan.setdefault("path", str(args.plan))
        source_plan.setdefault("sha256", plan_sha)
        source_plan.setdefault("bundle_input_path", str(args.bundle))
        source_plan["archived_path"] = str(run_dir / "plan.md")
        write_json(bundle_out_path, bundle_payload)
    else:
        bundle_out_path = args.bundle

    try:
        parent, items, _ = load_issue_bundle(bundle_out_path, spec_mode=config.spec_mode)
    except IssueBundleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except OSError as exc:
        print(f"ERROR: failed to read bundle: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    issue_client = GitHubIssueClient(context.repo, github_host=context.host)
    try:
        feature_issue_type_id = require_issue_type_id(
            owner=context.repo_owner,
            name=context.repo_name,
            issue_type_name=config.parent_issue_type,
        )
    except GhCliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(SETUP_HINT, file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        parent_form = load_issue_form(args.parent_template)
        require_field_ids(
            form=parent_form,
            required=mapped_field_ids(config.data["fields"], "parent", config.spec_mode),
        )
    except IssueFormError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    return (
        context, plan_key, plan_dir, run_id, plan_sha, bundle_hash,
        bundle_out_path, sync_out_path, parent, items,
        issue_client, feature_issue_type_id, parent_form,
    )


def _handle_dry_run(
    *,
    args: argparse.Namespace,
    context: Any,
    parent: Any,
    items: list[Any],
    parent_form: IssueForm,
    plan_key: str,
    run_id: str,
    plan_sha: str,
    bundle_out_path: Path,
) -> int:
    owner_by_item_id = {item.id: item.id for item in items}
    try:
        coverage_preview = _build_coverage_matrix(
            atom_registry=parent.atom_registry,
            items=items,
            owner_by_item_id=owner_by_item_id,
        )
    except PlanSyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parent_body = render_parent_body(
        form=parent_form,
        change_id=f"{PARENT_CHANGE_ID_PREFIX}-{plan_key}",
        plan_key=plan_key,
        run_id=run_id,
        objective=parent.objective,
        scope=parent.scope,
        assumptions=parent.assumptions,
        atom_registry=parent.atom_registry,
        coverage_matrix=coverage_preview,
        source_plan_path=str(args.plan),
        source_plan_sha256=plan_sha,
        child_issue_numbers=[],
        planned_child_ids=[item.id for item in items],
        field_mapping=args.workflow_config.data["fields"],
    )
    try:
        result = sync_bundle(
            bundle_path=bundle_out_path,
            repo=context.repo,
            repo_owner=context.repo_owner,
            repo_name=context.repo_name,
            issue_template=args.issue_template,
            plan_key=plan_key,
            run_id=run_id,
            sync_state_path=None,
            dry_run=True,
            spec_mode=args.workflow_config.spec_mode,
            field_mapping=args.workflow_config.data["fields"],
            work_issue_type=args.workflow_config.work_issue_type,
            github_host=context.host,
        )
    except GhCliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(SETUP_HINT, file=sys.stderr)
        return 1
    except (SyncError, GitHubIssueError, IssueBundleError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    result["parent_body"] = parent_body
    result["parent_preview"] = parent_body.splitlines()[:18]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _handle_existing_run(
    *,
    args: argparse.Namespace,
    context: Any,
    existing_sync: dict[str, Any],
    parent: Any,
    items: list[Any],
    issue_client: GitHubIssueClient,
    feature_issue_type_id: str,
    parent_form: IssueForm,
    plan_key: str,
    run_id: str,
    plan_sha: str,
) -> int:
    children = _child_numbers(existing_sync.get("items", []))
    owner_by_item_id = _owner_map(existing_sync.get("items", []))
    try:
        coverage_matrix = _build_coverage_matrix(
            atom_registry=parent.atom_registry,
            items=items,
            owner_by_item_id=owner_by_item_id,
        )
    except PlanSyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    try:
        parent_result = _ensure_parent_issue(
            issue_client=issue_client,
            feature_issue_type_id=feature_issue_type_id,
            parent_form=parent_form,
            plan_key=plan_key,
            run_id=run_id,
            parent_title=parent.title,
            parent_objective=parent.objective,
            parent_scope=parent.scope,
            parent_assumptions=parent.assumptions,
            parent_atom_registry=parent.atom_registry,
            parent_coverage_matrix=coverage_matrix,
            source_plan_path=str(args.plan),
            source_plan_sha256=plan_sha,
            child_issue_numbers=children,
            field_mapping=args.workflow_config.data["fields"],
        )
        _reconcile_sub_issues(
            repo=context.repo,
            parent_number=int(parent_result["issue_number"]),
            desired_child_numbers=[int(n) for n in children if isinstance(n, int)],
        )
    except PlanSyncError as exc:
        print(f"WARNING: {exc}", file=sys.stderr)

    if args.format == "json":
        print(json.dumps(existing_sync, indent=2, sort_keys=True))
        return 0
    rows = [
        (item["change_id"], item["issue_number"], item["url"])
        for item in existing_sync.get("items", [])
        if isinstance(item, dict)
    ]
    print(render_mapping_table(rows))
    return 0


def _sync_new_run(
    *,
    args: argparse.Namespace,
    context: Any,
    state: dict[str, Any],
    active: dict[str, Any],
    active_run_id: str,
    parent: Any,
    items: list[Any],
    issue_client: GitHubIssueClient,
    feature_issue_type_id: str,
    parent_form: IssueForm,
    plan_key: str,
    plan_dir: Path,
    run_id: str,
    plan_sha: str,
    bundle_hash: str,
    bundle_out_path: Path,
    sync_out_path: Path,
    state_path: Path,
) -> int:
    state["plan_key"] = plan_key
    state["pending"] = {
        "run_id": run_id,
        "bundle_sha256": bundle_hash,
        "bundle_path": _relative_to_plan_dir(plan_dir, bundle_out_path),
        "sync_path": _relative_to_plan_dir(plan_dir, sync_out_path),
    }
    write_json(state_path, state)

    try:
        new_sync = sync_bundle(
            bundle_path=bundle_out_path,
            repo=context.repo,
            repo_owner=context.repo_owner,
            repo_name=context.repo_name,
            issue_template=args.issue_template,
            plan_key=plan_key,
            run_id=run_id,
            sync_state_path=sync_out_path,
            dry_run=False,
            spec_mode=args.workflow_config.spec_mode,
            field_mapping=args.workflow_config.data["fields"],
            work_issue_type=args.workflow_config.work_issue_type,
            github_host=context.host,
        )
    except GhCliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(SETUP_HINT, file=sys.stderr)
        return 1
    except (SyncError, GitHubIssueError, IssueBundleError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if active_run_id and active_run_id != run_id:
        old_sync_path = active.get("sync_path", "") if isinstance(active.get("sync_path"), str) else ""

        old_sync: dict[str, Any] = {}
        if old_sync_path:
            try:
                old_sync = _safe_load_json(plan_dir / old_sync_path)
            except PlanSyncError as exc:
                print(f"WARNING: failed to load old sync file: {exc}", file=sys.stderr)

        try:
            _close_and_remove_old_run(
                old_sync=old_sync,
                new_sync=new_sync,
                repo=context.repo,
            )
        except (GhCliError, GitHubIssueError) as exc:
            print(f"WARNING: failed to cleanup old run: {exc}", file=sys.stderr)

    children = _child_numbers(new_sync.get("items", []))
    owner_by_item_id = _owner_map(new_sync.get("items", []))
    try:
        coverage_matrix = _build_coverage_matrix(
            atom_registry=parent.atom_registry,
            items=items,
            owner_by_item_id=owner_by_item_id,
        )
    except PlanSyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parent_result: dict[str, Any] | None = None
    try:
        parent_result = _ensure_parent_issue(
            issue_client=issue_client,
            feature_issue_type_id=feature_issue_type_id,
            parent_form=parent_form,
            plan_key=plan_key,
            run_id=run_id,
            parent_title=parent.title,
            parent_objective=parent.objective,
            parent_scope=parent.scope,
            parent_assumptions=parent.assumptions,
            parent_atom_registry=parent.atom_registry,
            parent_coverage_matrix=coverage_matrix,
            source_plan_path=str(args.plan),
            source_plan_sha256=plan_sha,
            child_issue_numbers=[int(n) for n in children if isinstance(n, int)],
        )
        _reconcile_sub_issues(
            repo=context.repo,
            parent_number=int(parent_result["issue_number"]),
            desired_child_numbers=[int(n) for n in children if isinstance(n, int)],
        )
        state["parent_issue"] = {
            "issue_number": int(parent_result["issue_number"]),
            "url": str(parent_result["url"]),
            "issue_id": str(parent_result.get("issue_id", "")),
        }
    except PlanSyncError as exc:
        print(f"WARNING: {exc}", file=sys.stderr)

    state.pop("pending", None)
    state["active"] = {
        "run_id": run_id,
        "bundle_sha256": bundle_hash,
        "bundle_path": _relative_to_plan_dir(plan_dir, bundle_out_path),
        "sync_path": _relative_to_plan_dir(plan_dir, sync_out_path),
    }
    write_json(state_path, state)

    if args.format == "json":
        if parent_result is not None:
            new_sync["parent_issue"] = state.get("parent_issue")
        print(json.dumps(new_sync, indent=2, sort_keys=True))
        return 0

    if isinstance(state.get("parent_issue"), dict) and state["parent_issue"].get("url"):
        print(f"parent_issue: {state['parent_issue']['url']}\n")
    rows = [
        (item["change_id"], item["issue_number"], item["url"])
        for item in new_sync.get("items", [])
        if isinstance(item, dict)
    ]
    print(render_mapping_table(rows))
    return 0


def main() -> int:
    args = _parse_args()

    if not args.dry_run:
        if args.approved_bundle is None:
            print("ERROR: --approved-bundle is required for a live sync", file=sys.stderr)
            return 1
        try:
            config = _workflow_config(args)
            current_bundle = _safe_load_json(args.bundle)
            load_approved_bundle(args.approved_bundle, current_bundle, config.spec_mode)
        except (ApprovalError, ConfigError, PlanSyncError) as exc:
            print(f"ERROR: approval verification failed: {exc}", file=sys.stderr)
            return 1

    (
        context, plan_key, plan_dir, run_id, plan_sha, bundle_hash,
        bundle_out_path, sync_out_path, parent, items,
        issue_client, feature_issue_type_id, parent_form,
    ) = _prepare_run(args, persist=not args.dry_run)

    if args.dry_run:
        return _handle_dry_run(
            args=args,
            context=context,
            parent=parent,
            items=items,
            parent_form=parent_form,
            plan_key=plan_key,
            run_id=run_id,
            plan_sha=plan_sha,
            bundle_out_path=bundle_out_path,
        )

    state_path = plan_dir / STATE_FILENAME
    state = _safe_load_json(state_path)
    active = state.get("active", {}) if isinstance(state.get("active"), dict) else {}
    raw_active_run_id = active.get("run_id")
    active_run_id = raw_active_run_id if isinstance(raw_active_run_id, str) else ""

    existing_sync = _safe_load_json(sync_out_path)
    if (
        not args.force_new_run
        and active_run_id == run_id
        and existing_sync.get("status") == "complete"
    ):
        return _handle_existing_run(
            args=args,
            context=context,
            existing_sync=existing_sync,
            parent=parent,
            items=items,
            issue_client=issue_client,
            feature_issue_type_id=feature_issue_type_id,
            parent_form=parent_form,
            plan_key=plan_key,
            run_id=run_id,
            plan_sha=plan_sha,
        )

    return _sync_new_run(
        args=args,
        context=context,
        state=state,
        active=active,
        active_run_id=active_run_id,
        parent=parent,
        items=items,
        issue_client=issue_client,
        feature_issue_type_id=feature_issue_type_id,
        parent_form=parent_form,
        plan_key=plan_key,
        plan_dir=plan_dir,
        run_id=run_id,
        plan_sha=plan_sha,
        bundle_hash=bundle_hash,
        bundle_out_path=bundle_out_path,
        sync_out_path=sync_out_path,
        state_path=state_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
