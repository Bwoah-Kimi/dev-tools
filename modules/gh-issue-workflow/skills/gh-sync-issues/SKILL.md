---
name: gh-sync-issues
description: "Use when synchronizing a reviewed and approved issue bundle to GitHub, including parent/work issues, native sub-issues, and Blocked-by dependencies."
---

# GitHub Sync Issues

Live GitHub write only. Planning, rendering, and independent review happen in `gh-plan-to-issues`.

## Preconditions

- Require the plan, current bundle, and its `approved-bundle.json` metadata on disk.
- Read `.agents/gh-issue-workflow/config.json` and `project-context.md`; use configured issue types, field mappings, paths, and specification policy.
- Require clean bundle validation and current-revision bundle approval.
- Run preflight. Stop on missing authentication, repository mismatch, unavailable issue types/templates, or native API support.

## Revision guard

Verify the approval before any cache, archive, state, or remote write:

```bash
python3 .agents/skills/_shared/approval.py verify --bundle /path/to/bundle.json --approved-bundle /path/to/review/approved-bundle.json --spec-mode <configured-mode>
```

A hash, content, or policy mismatch requires a new review. Never bypass this check.

## Sync

```bash
python3 .agents/skills/gh-sync-issues/scripts/gh_sync_plan.py --plan /path/to/plan.md --bundle /path/to/bundle.json --approved-bundle /path/to/review/approved-bundle.json
```

The sync archives formal runs below the configured plan output root, creates or resumes work issues, reconciles native blocked-by links, upserts the parent, reconciles native sub-issues, and handles superseded runs. Existing `CHANGE_ID` and run-state semantics remain intact.

Return the parent URL, work-item mapping, dependency reconciliation result, and any errors. Do not report success when a step failed. Merge is never part of sync.
