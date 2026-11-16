---
name: gh-work-queue
description: "Use when inspecting the GitHub Task queue, finding the next ready Task issue, rendering a PR body, or driving a Task issue through implementation, review, merge, and closure."
---

# GitHub Work Queue

## Workflow

Queue membership is GitHub **Issue Type = `Task`** (no issue-body membership checks). Ordering is deterministic by ascending GitHub issue number.

Readiness:
- `--ready` means all GitHub-native **Blocked by** issues are `CLOSED`.

In progress:
- An issue is treated as in-progress if it has an `OPEN` PR that references it via closing keywords (exposed by `closedByPullRequestsReferences`).

### Routing

Use the user’s wording to jump to the right subsection:
- "work queue" / "task queue" / "list ready tasks" / "preview queue" → **Preview queue**
- "what's next" / "next ready task" / "next task issue" → **Next ready task**
- "show #123" / "show issue #123" / "inspect issue 123" → **Show issue N**
- "render PR body" / "PR template text" → **Render PR body**
- "merge PR" / "review threads" / "resolve review threads" → **Merge + close loop**
- "execute" / "implement" / "do this issue" → **Execute issue** (after fetching JSON; stops at the open PR — merge + close is off by default)
- "execute and merge" / "auto-merge" / "merge too" → **Execute issue** with merge enabled (run **Merge + close loop** once the PR is open)

Merge + close is opt-in: it never runs automatically. Reach it only when the user invokes it directly ("merge PR") or explicitly enables it for an execute run.

### Preview queue (`preview`)

- [ ] Run: `python3 .agents/skills/gh-work-queue/scripts/gh_work_queue.py list --ready --format table`

### Next ready task (`next`)

- [ ] Run: `python3 .agents/skills/gh-work-queue/scripts/gh_work_queue.py next --ready --format json`
- [ ] Capture from JSON: `issue_number`, `title`, `url`, `blocked_by`, `closing_prs`, `body`, `parent_issue`.
- [ ] If the user asked to execute the issue, continue to **Execute issue**.

### Show issue N (`issue N`)

- [ ] Run: `python3 .agents/skills/gh-work-queue/scripts/gh_work_queue.py show --issue N --format json`
- [ ] Capture from JSON: `issue_number`, `title`, `url`, `blocked_by`, `closing_prs`, `body`, `parent_issue`.
- [ ] If the user asked to execute the issue, continue to **Execute issue**.

### Render PR body (`pr-body`)

- [ ] Run: `python3 .agents/skills/gh-work-queue/scripts/gh_work_queue.py pr-body --issue N --specs-changed "<fill>" --tests-run "<fill>"`

### Execute issue (issue → PR; merge → closed is opt-in)

- [ ] Context economy: dispatch prompts and re-dispatches carry the issue number plus the specific finding only — never paste prior reports, earlier review findings, or raw validation output.
- [ ] Check `out/gh-work-queue/progress.md` (if it exists). If this issue is already marked closed there, skip it — do not re-dispatch.
- [ ] Use the current Task issue as the executable proposal and the `parent_issue` object as the overall objective, assumptions, and atom-coverage boundary.
  - [ ] If `parent_issue` is `null`, stop and ask the user whether this Task is intentionally outside the normal Feature → Task flow.
  - [ ] Require an implementation-ready plan, a behavior-complete `## Intent and Contract`, and `## Expected Spec Impact`. Do not execute old-format Tasks through a compatibility path.
- [ ] Session preflight (once per session): dispatch the `gh-preflight` subagent with scope `work-queue` to verify GitHub access. Reuse `READY`; stop and surface `BLOCKED` remediation.
- [ ] Build environment (once per session, after preflight): dispatch the `build-env-runner` subagent (the `build-env` skill), capture its env exports, `uv run --extra dev` prefix, baseline, and caveats, then reuse them for validation. Do not send build logs or controller-only environment setup to the implementer.
- [ ] Start from an up-to-date base branch, then create/switch to one issue branch. Work on one Task issue per branch/PR.
- [ ] Dispatch the `gh-implementer` subagent with `ISSUE_NUMBER`. The implementer fetches the current Task + parent with `gh_work_queue.py show`, reads cited repo files, and works from those sources of truth.
- [ ] The implementer reads the current canonical specs as the behavioral baseline, implements production code and tests first, then reconciles specs before reporting `DONE`:
  - [ ] Treat `Expected Spec Impact` paths as planning guidance, not a pre-authored or exhaustive requirement delta.
  - [ ] After behavior stabilizes, edit every canonical spec needed to describe the intentional observable or cross-component contract. Do not promote incidental algorithms, helpers, or test placement into behavior specs.
  - [ ] An explicit no-impact rationale means verify that implementation preserves canonical behavior; do not churn specs merely to mention the Task.
  - [ ] Run focused strict OpenSpec validation after reconciliation. The final implementation, tests, and canonical specs must agree before review.
- [ ] Handle the implementer status before review:
  - [ ] `DONE` → continue to validation.
  - [ ] `DONE_WITH_CONCERNS` → resolve or explicitly accept every concern before review.
  - [ ] `NEEDS_CONTEXT` → treat the report as evidence and a request for direction, not as a prescribed remedy:
    - [ ] Inspect the Task, parent, cited references, and repository. If they already provide an authoritative answer, re-dispatch the issue number plus the exact need and answer.
    - [ ] If no authoritative answer exists, sources conflict, implementation appears infeasible, or human judgment is required, surface the implementer's `Need`, `Evidence`, `Impact`, `Options`, and `Recommendation` unchanged in the main thread and pause.
    - [ ] Follow the main-thread decision: answer and re-dispatch, amend and re-review the Task, split or replace it, add a dependency, or stop. Do not silently reinterpret the contract or force a predetermined remedy.
  - [ ] `BLOCKED` → stop and surface an external access, tooling, or environment blocker instead of guessing.
- [ ] Apply the same status handling after every implementer re-dispatch, including validation failures, internal review findings, and GitHub review feedback.
- [ ] Build the controller-owned validation list from the Task acceptance checks, repository quality gates, `openspec validate --all --strict --no-interactive`, build-env exports/prefix, and any stronger commands the implementer proposed.
- [ ] Validate via `gh-validation-runner` after implementation commits, using `out/gh-work-queue/execute/ISSUE_NUMBER/logs/`.
  - [ ] `FAIL` → route the specific failures (reference the log-file paths; do not paste raw output) back through the implementer role, then re-run the runner until it passes.
  - [ ] `PASS` → continue to review.
- [ ] Prepare a review packet at `out/gh-work-queue/review/ISSUE_NUMBER/packet.md`. Give the reviewers only this packet plus the diff:
  - [ ] `## Parent Issue` → paste `parent_issue.body`.
  - [ ] `## Task Issue` → paste the Task issue body.
  - [ ] `## References` → list the repo-relative paths you actually read, or `(none)`.
  - [ ] `## Spec Reconciliation` → list expected versus actually changed canonical spec paths and briefly justify every expected path left unchanged, every unexpected path changed, or why no spec changed.
  - [ ] `## Validation Evidence` → record the `gh-validation-runner` compact result (`cmd → PASS/FAIL`) and the log-dir path. Do not paste raw command output.
  - [ ] `## Diff File` → generate the diff file by running `bash .agents/skills/gh-work-queue/scripts/review_package.sh BASE_SHA HEAD_SHA ISSUE_NUMBER` and record the output path. Do not paste diff content into the packet or your own context.
  - [ ] Do **not** include implementation chat, scratch reasoning, or confidence claims in the packet.
- [ ] Dispatch the `gh-spec-reviewer` subagent with the review packet (include the diff file path).
- [ ] The spec review must verify that the implementation satisfies `Intent and Contract`, that the final canonical specs capture all intentional behavior without incidental implementation detail, and that implementation/tests/specs agree. `Expected Spec Impact` is guidance: require an explanation when a listed path remains unchanged or an unlisted path changes, but judge the result against the approved contract rather than the forecast.
- [ ] Resolve each `⚠️ Cannot verify from diff` item yourself — you hold the cross-issue context the reviewer lacks. If you confirm a gap, treat it as a failed spec review and route back to the implementer.
- [ ] If spec review finds issues:
  - [ ] Route all `Critical` and `Important` findings back through the implementer role, not through same-session edits.
  - [ ] If a finding is unclear, clarify it before making code changes.
  - [ ] Verify reviewer claims against the issue, specs, and codebase instead of accepting them blindly.
  - [ ] If a finding is incorrect, push back with concrete reasoning instead of making a fake fix.
  - [ ] Fix findings in coherent batches, rerun affected validation, refresh the review packet, and re-dispatch spec reviewer until approved.
- [ ] Dispatch the `gh-code-reviewer` subagent with the refreshed review packet (include the diff file path; regenerate the diff if fixes changed the range).
- [ ] If code review finds issues:
  - [ ] Route all `Critical` and `Important` findings back through the implementer role, rerun affected validation, refresh the review packet, and re-dispatch code reviewer until approved.
  - [ ] If code-quality fixes materially change behavior, requirements coverage, or cited refs, rerun spec review before proceeding.
- [ ] If the harness cannot dispatch subagents, stop and surface that limitation instead of collapsing review into the main session.
- [ ] Render the PR body with the actual changed canonical spec paths (or `(none; <reason>)`) and the real validation commands that passed after the latest fix round.
- [ ] Create a PR that links the issue (include `Fixes #ISSUE_NUMBER`).
- [ ] Merge + close is OFF by default. Once the PR is open, append one line to `out/gh-work-queue/progress.md`: `#ISSUE_NUMBER: pr-open (PR #N, awaiting merge)`, report the PR URL, and stop here — leave merge + close to the user (manual, or a later explicit merge request).
- [ ] Only when merge is enabled for this run (the user asked to "execute and merge" / "auto-merge", or invokes merge directly) continue to **Merge + close loop**.
- [ ] Never re-dispatch an issue the progress ledger already marks closed — check the ledger and `git log` after any context compaction.

### Merge + close loop (`merge`)

This step is opt-in and never runs automatically. Reach it only when the user invokes it directly ("merge PR #N") or explicitly enables merge for an **Execute issue** run. Like the implementer and reviewers, the controller drives it through a subagent rather than running the loop inline.

- [ ] Dispatch the `gh-merge-closer` subagent with `PR_NUMBER` and `ISSUE_NUMBER` (for a standalone "merge PR #N", resolve `ISSUE_NUMBER` from the PR's closing-issue reference). No packet to assemble: the worker reads PR state, base branch, repo merge method, and review threads from GitHub itself, and its escalation and merge-gate rules live in its own definition.
- [ ] Handle the worker status:
  - [ ] `MERGED` → it confirmed the issue is `CLOSED`. Append one line to `out/gh-work-queue/progress.md`: `#ISSUE_NUMBER: closed (PR #N, commits base7..head7)`, then return to the updated base branch.
  - [ ] `NEEDS_CODE_CHANGE` → for each escalated thread, route the issue number plus the specific thread context through the implementer role, rerun affected validation via the `gh-validation-runner` subagent, and refresh the review packet. If the change materially affects behavior or requirements coverage, rerun the staged review flow (spec → code). Push the fixes, then re-dispatch `gh-merge-closer`.
  - [ ] `BLOCKED` → surface the blocker (failing required checks, a merge conflict needing a decision, a missing approval) instead of forcing the merge. Do not use `--admin`.
- [ ] If the harness cannot dispatch subagents, surface that limitation; the documented merge steps live in the `gh-merge-closer` definition and can be run manually instead of collapsing them into automated session state.
- [ ] Do not start the next queue item until merge is complete, unresolved review threads are at zero, and the issue is confirmed closed.
