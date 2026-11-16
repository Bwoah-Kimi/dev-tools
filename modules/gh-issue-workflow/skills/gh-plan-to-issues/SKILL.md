---
name: gh-plan-to-issues
description: "Use when turning a written implementation plan into a gh-plan-to-issues bundle, or when validating and refining an existing bundle before GitHub sync."
---

# GitHub Plan To Issues

## Functions

- [ ] `scripts/gh_validate_bundle.py` - Validate a `gh-plan-to-issues` bundle before sync

### Routing

Use the user’s wording to jump to the right subsection:
- "break down plan" / "plan to issues" / "create issues from plan" → **Author or refine a bundle**
- "validate bundle" / "bundle validation" / "fix bundle" / "review bundle" / "approve bundle" → **Validate, render, review, and approve**
- "dry-run" / "preview issue bodies" / "render issues" → **Validate, render, review, and approve** (below)
- "sync issues" / "create issues in GitHub" / "update issues" → hand the **approved** bundle to **`gh-sync-issues`**

### Author or Refine a Bundle

- [ ] Establish the source plan file verbatim → see **Establish plan file**.
- [ ] Author or update `bundle.json` → see **Author bundle.json**.
- [ ] Validate, render, review, and approve the bundle → see **Validate, render, review, and approve**.

### Establish plan file (verbatim)

- [ ] Ensure the plan exists on disk *verbatim* **before** reading `.github/ISSUE_TEMPLATE/*` (prevents long-context drift).
- [ ] If the plan already exists as a markdown file: use that path as `--plan`.
- [ ] If the plan is provided in chat (including `<proposed_plan>...</proposed_plan>`):
  - [ ] Choose a deterministic date-prefixed `plan_key` in the format `YYYY-MM-DD-<kebab-slug>`.
  - [ ] Write the plan to `out/gh-plan-to-issues/<plan_key>/<plan_key>.md` using a single heredoc (no edits, no rewrapping):
        - [ ] `mkdir -p out/gh-plan-to-issues/<plan_key>`
        - [ ] `cat <<'EOF' > out/gh-plan-to-issues/<plan_key>/<plan_key>.md` (paste plan verbatim) `EOF`
- [ ] Hard rule: do **not** read `.github/ISSUE_TEMPLATE/*` until the plan file exists.

### Author bundle.json

- [ ] Read the issue form templates (treat `attributes.description` as normative guidance):
  - Parent: `.github/ISSUE_TEMPLATE/parent_issue.yml`
  - Sub-issue: `.github/ISSUE_TEMPLATE/sub_issue.yml`
- [ ] Build **Plan Atoms**:
  - [ ] Decompose the plan into atomic, single-intent, independently checkable requirements.
  - [ ] Encode atoms as stable IDs: `A1`, `A2`, ... (one requirement per atom).
  - [ ] Categories to cover: behavior/API semantics, implementation constraints, docs/spec obligations, tests/verification, assumptions/defaults.
- [ ] Decompose the plan into 1 parent issue (tracks objective/scope/assumptions + atom registry) and N sub-issues (executable work items).
- [ ] Assign **ownership**:
  - [ ] Every atom MUST be owned by at least one sub-issue.
  - [ ] Each sub-issue MUST list the atoms it owns (with brief rationale).
- [ ] Make each sub-issue executable for an implementer with little local context:
  - [ ] `intent_and_contract` states the intended observable behavior, constraints, and invariants completely enough that implementation does not silently choose a new contract.
  - [ ] `spec_impact` explains which canonical behavior specs are likely to need reconciliation after implementation; an empty path list has a concrete rationale for preserving all canonical behavior.
  - [ ] `implementation_plan` is implementation-ready, not a vague suggestion: establish feasibility and interactions while naming any bounded choices the implementer may resolve.
  - [ ] `file_and_interface_scope` uses exact repo paths when known, or explicit discovery commands when not.
  - [ ] `acceptance_checks` are observable pass/fail outcomes, not aspirations.
  - [ ] `assumptions_defaults` captures real assumptions and chosen defaults; use `(none)` only when truly empty.
  - [ ] `references` match the issue's "how": for a pure mechanical edit (move/rename/layout) the plan already determines, use `references: []` and do not restate the how; for an issue that realizes a design pattern, cite the exemplar as `path:line` plus one line naming what to mirror, and optionally add a shape-only sketch (signatures/skeleton/dispatch structure, never full bodies) with the exemplar `path:line` as the source of truth.
- [ ] Keep issue boundaries coherent and self-sufficient:
  - [ ] Do not mix unrelated work into one sub-issue just to reduce issue count.
  - [ ] Do not duplicate the same atom across multiple sub-issues unless shared ownership is genuinely required.
  - [ ] Split only where a reviewer could reject one sub-issue while approving its neighbor; fold scaffolding, setup, and docs into the sub-issue whose deliverable needs them.
  - [ ] Each sub-issue must be completable from its own `file_and_interface_scope` + its `dependencies` + the base repo. If an owned atom needs an artifact a sibling produces, add a `dependencies` edge; if it still is not self-sufficient, the boundary is wrong — redraw it.
  - [ ] Encode every ordering, data, and spec-state dependency as a `dependencies` edge. The work-queue readiness gate reads only `dependencies`, never prose. If the plan's ordering is ambiguous, ask the user rather than guessing.
  - [ ] If Tasks expect to touch the same spec path, verify their intended contracts do not conflict and encode an ordering dependency when one consumes the other's behavior.
- [ ] Write `bundle.json` using the schema below (recommended path: `out/gh-plan-to-issues/<plan_key>/bundle.json`).

### Reconcile specs after implementation

GitHub issues are the reviewed proposal output. The work queue does not create a second OpenSpec proposal. It implements the approved contract first, then edits canonical `openspec/specs/**/spec.md` files on the same branch before review.

- [ ] Put the approved behavior in `intent_and_contract` and observable scenarios in `acceptance_checks`; do not pre-author an exact ADD/MODIFY/REMOVE requirement delta inside the issue.
- [ ] In `spec_impact.spec_paths`, list the canonical specs likely to need reconciliation. Treat these paths as planning guidance, not an exhaustive or authoritative final delta.
- [ ] For expected no-spec-impact work, use `spec_paths: []` and explain why all current behavior contracts should remain unchanged.
- [ ] Keep implementation algorithms, helper structure, and incidental test placement in the implementation plan or code review. Promote them into canonical specs only when they are intentional, verifiable repository or cross-component contracts.
- [ ] Do not emit a separate post-implementation spec Task. Reconcile behavior specs in the implementation Task that makes the behavior real.

### Validate, render, review, and approve

- [ ] Run structural validation and fix until clean: `python3 .agents/skills/gh-plan-to-issues/scripts/gh_validate_bundle.py --bundle /path/to/bundle.json`
  - [ ] Enforces atom coverage and canonical expected-spec path shape. Shared paths produce a warning; the mandatory bundle review decides whether the contracts conflict or require an ordering dependency.
- [ ] Dispatch the `gh-preflight` subagent with scope `sync`; the dry-run render resolves the repo and the Feature issue-type, so it needs read access. If it reports `BLOCKED`, surface the remediation and stop.
- [ ] Dry-run render: `python3 .agents/skills/gh-sync-issues/scripts/gh_sync_plan.py --plan /path/to/plan.md --bundle /path/to/bundle.json --dry-run`
  - [ ] Read the render before claiming ready. If it drops scope, renders malformed bodies, or shows the wrong dependency picture, fix the bundle and re-validate + re-render.
- [ ] Build a review packet at `<bundle dir>/review/packet.md` — give the reviewer only this packet:
  - [ ] `## Source Plan Path`, `## Source Plan` (verbatim), `## Bundle Path`, `## Bundle JSON` (verbatim), `## Parent Template Path` (`.github/ISSUE_TEMPLATE/parent_issue.yml`), `## Sub-issue Template Path` (`.github/ISSUE_TEMPLATE/sub_issue.yml`), `## Bundle Validation Result` (latest real output), `## Dry-Run Render Output` (latest real output).
  - [ ] Do **not** include session history, scratch reasoning, or "I think this is ready" language.
- [ ] Dispatch the `gh-bundle-reviewer` subagent with the packet. Its tool-native definition (`.codex/agents/gh-bundle-reviewer.toml` / `.claude/agents/gh-bundle-reviewer.md`) owns model selection; do not inherit the root session's model by accident.
  - [ ] Bundle-structure or missing-atom problems → fix here, re-validate + re-render, then re-dispatch.
  - [ ] Re-dispatch until the reviewer approves the current revision. If the harness cannot dispatch subagents, stop and surface that limitation.
- [ ] On approval, pin the approved revision for the sync guard: `cp /path/to/bundle.json <bundle dir>/review/approved-bundle.json`.
- [ ] Hand off to `gh-sync-issues` for **live sync only**: pass the plan path, the bundle path, and `<bundle dir>/review/approved-bundle.json`. Do not claim GitHub issues exist yet.

## JSON Bundle Schema

GitHub issues ultimately store a Markdown body. The JSON bundle is an intermediate input; scripts render the final Markdown using the YAML issue form templates (field order/labels) plus bundle content.

Write a JSON object with:

- `parent`: object with:
  - `title`: string
  - `objective`: string
  - `scope`: list of strings
  - `assumptions`: list of strings
  - `atom_registry`: list of strings (non-empty; each entry starts with `A<number>:`)
- `items`: list of objects (sub-issues), each with:
  - `id`: stable token within the bundle (recommend `S1`, `S2`, …)
  - `title`: GitHub issue title
  - `intent_and_contract`: markdown string (intent + externally visible behavior/contracts)
  - `owned_atoms`: list of strings (non-empty; each starts with `A<number>:`)
  - `spec_impact`: object with:
    - `rationale`: non-empty string explaining the expected relationship to current canonical behavior specs, including why no spec change is expected when the path list is empty
    - `spec_paths`: list of likely canonical `openspec/specs/**/spec.md` paths; use an empty list when no behavior spec should change
  - `implementation_plan`: markdown string (implementation-ready approach plus bounded choices)
  - `file_and_interface_scope`: markdown string (explicit scope + concrete repo paths/interfaces)
  - `acceptance_checks`: list of bullet strings (non-empty; each references atom IDs like `[A3]`)
  - `assumptions_defaults`: markdown string (use `(none)` if not applicable)
  - `references`: optional list of strings
  - `handoff_contract`: markdown string stating **Consumes** (what this issue needs from sibling issues — each Consumes item MUST also appear in `dependencies`) and **Produces** (what later issues rely on from it); use `(none)` only if the issue is genuinely standalone
  - `dependencies`: optional list of tokens (`S2`, `#123`, …)
