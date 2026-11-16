---
name: gh-sync-issues
description: "Use when syncing an approved gh-plan-to-issues bundle to GitHub (create/update issues, reconcile Blocked-by)."
---

# GitHub Sync Issues

Live GitHub write only. Rendering and review happen in `gh-plan-to-issues`; this skill takes an already-approved bundle and makes GitHub match it.

## Functions

- [ ] `scripts/gh_sync_plan.py` - Live-sync a validated, approved bundle
- [ ] `scripts/gh_sync_issues.py` - Sub-issue sync implementation used by `gh_sync_plan.py`

## Routing

Use the user's wording to jump to the right subsection:
- "sync issues" / "create issues in GitHub" / "update issues" / "push bundle" → **Sync**
- "dry-run" / "render issues" / "review bundle" / "break down plan" / "author bundle" / "validate bundle" → use **`gh-plan-to-issues`**, not this skill

## Preconditions

- [ ] Require a plan path, a bundle path, and the approval record `<bundle dir>/review/approved-bundle.json`, all already on disk.
- [ ] Require the bundle to have passed `gh_validate_bundle.py` and `gh-bundle-reviewer` approval in `gh-plan-to-issues`.
- [ ] Keep the bundle format and output layout unchanged: `out/gh-plan-to-issues/<plan_key>/...`.

## Sync

- [ ] Revision guard — refuse to sync a bundle that changed since approval:
  - [ ] Structural gate: `python3 .agents/skills/gh-plan-to-issues/scripts/gh_validate_bundle.py --bundle /path/to/bundle.json` (must be clean).
  - [ ] Revision check: `diff -q /path/to/bundle.json <bundle dir>/review/approved-bundle.json`. If it differs, the bundle changed after approval — stop and send it back to `gh-plan-to-issues` for re-review. Do not sync.
- [ ] Dispatch the `gh-preflight` subagent with scope `sync`. If it reports `BLOCKED`, stop and surface the remediation instead of running `gh_sync_plan.py`.
- [ ] Run: `python3 .agents/skills/gh-sync-issues/scripts/gh_sync_plan.py --plan /path/to/plan.md --bundle /path/to/bundle.json`
- [ ] For details on what sync does (run archival, parent/sub-issue updates, dependency reconciliation via GitHub-native Blocked by links), see: `python3 .agents/skills/gh-sync-issues/scripts/gh_sync_plan.py --help`
- [ ] Return the parent issue, sub-issue mapping, and any dependency or reconciliation errors. Do not stop at "sync complete."
