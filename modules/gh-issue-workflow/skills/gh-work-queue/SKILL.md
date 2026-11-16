---
name: gh-work-queue
description: "Use when inspecting a repository's configured GitHub work queue, finding ready work, rendering a PR body, or driving work through implementation, review, optional merge, and closure."
---

# GitHub Work Queue

Read `.agents/gh-issue-workflow/config.json` and `project-context.md` first. Queue membership uses the configured work Issue Type; the parent type, paths, validation commands, agent roles, and PR policy also come from that profile. Run `gh-workflow-init` if the profile is missing.

Ready means every native Blocked-by issue is closed. In progress means an open PR references the work issue through a closing keyword. Ordering is by ascending issue number.

## Routing

- List/preview queue: `python3 .agents/skills/gh-work-queue/scripts/gh_work_queue.py list --ready --format table`
- Next ready item: `python3 .agents/skills/gh-work-queue/scripts/gh_work_queue.py next --ready --format json`
- Inspect one item: `python3 .agents/skills/gh-work-queue/scripts/gh_work_queue.py show --issue N --format json`
- Render PR body: `python3 .agents/skills/gh-work-queue/scripts/gh_work_queue.py pr-body --issue N --specs-changed "ACTUAL_SPECS" --tests-run "REAL_COMMANDS"`
- Execute: follow **Execute issue** below and stop after opening the PR.
- Merge: only a direct user request such as `merge PR #N` or an explicit execute-and-merge request enables **Merge + close**.

## Execute issue

1. Check the configured queue ledger. If the issue is recorded closed, do not redispatch it. Verify the ledger against `git log` after context compaction.
2. Fetch the work item and parent as JSON. If no parent exists, ask whether this item intentionally sits outside the normal parent/work flow.
3. Require an implementation-ready plan, behavior-complete contract, acceptance checks, and the spec fields required by the configured `spec_policy`.
4. Run GitHub preflight once per session. Then run each configured `validation.setup` command once per session and capture its result. Stop on `BLOCKED` or setup failure.
5. Start from an up-to-date base and use one issue branch and one PR per work item.
6. Dispatch the configured implementer with the issue number. The implementer fetches current issue/parent content and reads cited files plus required documents from `project-context.md`.
7. Handle implementer status:
   - `DONE`: continue to validation.
   - `DONE_WITH_CONCERNS`: resolve or explicitly accept every concern first.
   - `NEEDS_CONTEXT`: inspect authoritative sources. Answer and redispatch only when they resolve the need; otherwise present the need, evidence, impact, options, and recommendation to the user and pause.
   - `BLOCKED`: surface the external/tooling blocker without guessing.
8. Run every configured `validation.commands` entry after implementation commits, plus acceptance-specific commands proposed by the implementer. Store logs below the configured queue path. Route failures to the implementer by log path and rerun until they pass.

### Repository policy execution

- Read `config.json` and `project-context.md`; their configured validation commands and cited normative documents are the repository contract.
- For `spec_policy: openspec`, read current canonical specs, reconcile intentional behavior after implementation and tests, then run `openspec validate --all --strict --no-interactive`.
- For `spec_policy: optional`, reconcile each cited specification document. Run OpenSpec validation only for actual OpenSpec impacts; otherwise validate the cited documents using the configured commands.
- For `spec_policy: none`, do not require `spec_impact` and record `spec review: skipped by repository policy`. Do not claim a spec review occurred.
- Run every command in `validation.setup` once per session, then run every command in `validation.commands` after implementation. Preserve logs below the configured queue path.
- Merge remains opt-in. Never use `--admin`, bypass required checks, or merge with unresolved non-outdated review threads.

## Review and PR

1. Build a review packet below the configured queue path with the parent body, work-item body, actual references read, specification reconciliation/skipped reason, compact validation evidence with log paths, and diff file path. Exclude implementation chat and confidence claims.
2. Generate the diff with `review_package.sh BASE_SHA HEAD_SHA ISSUE_NUMBER QUEUE_OUTPUT_ROOT` and give reviewers the packet plus diff path, not a pasted diff.
3. For `openspec` and applicable `optional` impacts, dispatch the configured spec reviewer. Verify that implementation, tests, and normative documents agree. Investigate every unverifiable item with the controller's cross-issue context.
4. Dispatch the configured code reviewer after spec review when enabled. Verify findings against the repository before changing code. Route critical/important findings through the implementer, rerun affected validation, refresh the packet/diff, and rereview. Rerun spec review when fixes materially change behavior or requirement coverage.
5. If subagent dispatch is unavailable, stop and report the limitation instead of collapsing independent review into the main session.
6. Render the PR body using actual changed specification paths or the policy-aware no-change reason and the real passing validation commands. Create the PR using the configured close keyword.
7. Append `#ISSUE_NUMBER: pr-open (PR #N, awaiting merge)` to the configured queue ledger, report the PR URL, and stop unless merge was explicitly enabled.

## Merge + close

Merge is opt-in and never runs automatically. Dispatch the configured merge closer with PR and issue numbers. It must verify review threads, required checks, reviews, repository merge method, and issue closure. Admin bypass is forbidden.

- `MERGED`: confirm the issue is closed, record `#ISSUE_NUMBER: closed (PR #N, commits base7..head7)`, and return to the updated base branch.
- `NEEDS_CODE_CHANGE`: route each specific thread to implementation, rerun validation, refresh review evidence, and repeat the applicable spec/code reviews before retrying merge.
- `BLOCKED`: report failing checks, conflicts, missing approval, or other blocker. Do not force the merge.

Do not start another queue item until an explicitly enabled merge is complete and its issue is confirmed closed.
