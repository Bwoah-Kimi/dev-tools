---
name: gh-plan-to-issues
description: "Use when turning a written implementation plan into a validated issue bundle, or when reviewing and refining an existing bundle before GitHub sync."
---

# GitHub Plan To Issues

Turn a plan into one parent issue and executable work-item issues without embedding repository-specific policy in the generic engine.

## Repository context

- Read `.agents/gh-issue-workflow/config.json` and `.agents/gh-issue-workflow/project-context.md` before authoring. If they do not exist, use `gh-workflow-init` first.
- Use configured paths, issue types, templates, field mappings, and validation requirements. Resolve relative paths from the Git repository root.
- `plan_key` is a deterministic `YYYY-MM-DD-<kebab-slug>` value.

## Author or refine a bundle

1. Preserve the source plan verbatim under the configured plan output root before reading long templates. If the user supplied an existing Markdown file, use it directly.
2. Read the configured parent/work issue forms, including their field descriptions.
3. Decompose the plan into stable `A1`, `A2`, ... atoms. Cover behavior, constraints, documentation/spec obligations, tests, and assumptions.
4. Create one parent plus coherent work items. Every atom needs an owner; every ordering or data dependency must appear in `dependencies`, not only in prose.
5. Make each work item independently executable from its contract, implementation plan, scope, acceptance checks, references, handoff contract, and dependencies. Split items when one can be rejected while its neighbor is approved.

### Specification impact by policy

- `openspec`: every item requires `spec_impact`; paths must match `openspec/specs/**/spec.md`. Implementation reconciles canonical specs on the same branch.
- `optional`: every item requires `spec_impact`, but paths may be configured documentation/specification roots. An empty path list needs a concrete no-change rationale.
- `none`: `spec_impact` may be omitted. Do not invent a specification-review task or claim that spec reconciliation occurred.

Do not pre-author exact requirement deltas in the issue. Expected spec paths are planning guidance; implementation and acceptance checks own the approved behavior.

## Validate, render, review, and approve

1. Validate with the configured policy:

   ```bash
   python3 .agents/skills/gh-plan-to-issues/scripts/gh_validate_bundle.py --bundle /path/to/bundle.json --spec-mode <configured-mode>
   ```

   Add `--spec-root <path>` for every configured root when using `optional` with restricted roots.

2. Run read-only preflight and stop on `BLOCKED`.
3. Render without local or remote side effects:

   ```bash
   python3 .agents/skills/gh-sync-issues/scripts/gh_sync_plan.py --plan /path/to/plan.md --bundle /path/to/bundle.json --dry-run
   ```

4. Inspect the render for missing scope, malformed bodies, wrong types, and dependency errors. Fix and repeat validation/rendering.
5. Build a review packet containing the verbatim plan, verbatim bundle, actual template paths, latest validation output, and latest dry-run output. Exclude session history and unsupported confidence claims.
6. Dispatch the configured bundle reviewer. Re-review every changed revision until approved. If subagents are unavailable, stop and report the limitation.
7. Record the approved hash and policy:

   ```bash
   python3 .agents/skills/_shared/approval.py write --bundle /path/to/bundle.json --approved-bundle /path/to/review/approved-bundle.json --spec-mode <configured-mode>
   ```

8. Hand the plan, bundle, and approval record to `gh-sync-issues` for live sync only. Do not claim GitHub issues exist before sync succeeds.

## Bundle schema

The bundle is a JSON object:

- `parent`: `title`, `objective`, `scope`, `assumptions`, and nonempty `atom_registry`; each atom starts with `A<number>:`.
- `items`: nonempty list with stable `id`, `title`, `intent_and_contract`, `owned_atoms`, `implementation_plan`, `file_and_interface_scope`, `acceptance_checks`, `assumptions_defaults`, `references`, `handoff_contract`, and `dependencies`.
- `spec_impact`: required for `openspec` and `optional`, optional for `none`; contains a nonempty `rationale` and a `spec_paths` list.
- Acceptance checks must reference known atom IDs such as `[A3]`.
- Dependencies use item IDs or existing `#123` issue references.
