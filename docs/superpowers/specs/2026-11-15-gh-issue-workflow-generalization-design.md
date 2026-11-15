# GitHub Issue Workflow Generalization Design

**Date:** 2026-11-15

## Goal

Create a reusable `gh-issue-workflow` module in `dev-tools` that generalizes the three GitHub Issue workflow skills currently maintained in the `sw` repository:

- `gh-plan-to-issues`: turn a written implementation plan into a validated, reviewable issue bundle;
- `gh-sync-issues`: synchronize an approved bundle to GitHub, including parent/sub-issue relationships and native blocked-by dependencies;
- `gh-work-queue`: inspect the task queue and drive a task through implementation, validation, review, PR creation, optional merge, and closure.

The generalized module must preserve the complete workflow while removing dependencies on the `sw` repository, its product, and its build environment.

## Confirmed Decisions

- Preserve the complete workflow, including PR, review, merge, and closure orchestration.
- Keep `sw` unchanged. `dev-tools` will own an independent generalized copy, not a runtime patch over `sw` files.
- Use repository-local installation. Each target repository receives its own managed copy and configuration, so repositories can upgrade independently.
- Use incremental configuration-overlay generalization rather than rewriting the engine as a standalone package.
- Support three specification policies: `openspec`, `optional`, and `none`.

## Source Assessment

The source implementation does not hardcode the GitHub owner or repository name. Repository resolution already uses `--repo` or `gh repo view`. Its important couplings are instead workflow and environment conventions:

- parent and work issue types are fixed to `Feature` and `Task`;
- issue form paths, field IDs, and renderer behavior are fixed;
- `spec_impact` is mandatory and restricted to `openspec/specs/**/spec.md`;
- work-queue execution mandates OpenSpec reconciliation and strict validation;
- build setup assumes `build-env-runner`, `build-env`, and `uv run --extra dev`;
- linked native agents contain Zhen/LLVM-specific behavior and tool-specific model selections;
- output and cache paths are fixed and working-directory relative;
- cached repository context can override current-repository detection;
- several scripts rely on their exact directory depth, and tests import shared modules through a compatibility symlink;
- issue creation parses github.com URLs but not GitHub Enterprise hosts;
- the documented dry-run path can still write plan archives, bundles, state, or cache files;
- approval of a bundle is procedural in the skill prompt rather than verified by the sync implementation.

Generic atom parsing, bundle hashing, JSON/file helpers, GitHub CLI/GraphQL wrappers, sub-issue and blocked-by helpers, queue readiness, PR-thread inspection, and closure polling can be retained with targeted changes.

## Non-Goals

The first version will not:

- modify or migrate `sw`;
- require a standalone Python package, package registry, or independent release process;
- provide a label-based fallback for repositories without native Issue Types, sub-issues, and blocked-by relationships;
- automatically create a real repository, issue, PR, or merge during installation or tests;
- push a target repository or change its default branch;
- pin model choices for Claude or Codex agents;
- preserve Zhen, LLVM, or other product-specific build behavior in generic agents;
- silently maintain divergent skill copies when compatibility links cannot be created.

## Architecture

### Canonical Module

The canonical source lives at `modules/gh-issue-workflow`:

```text
modules/gh-issue-workflow/
├── skills/
│   ├── gh-plan-to-issues/
│   │   ├── SKILL.md
│   │   └── scripts/
│   ├── gh-sync-issues/
│   │   ├── SKILL.md
│   │   └── scripts/
│   ├── gh-work-queue/
│   │   ├── SKILL.md
│   │   └── scripts/
│   └── _shared/
├── agents/
│   ├── claude/
│   └── codex/
├── templates/
│   ├── config.json
│   ├── parent_issue.yml
│   ├── sub_issue.yml
│   └── pull_request_template.md
├── tests/
├── install/
│   └── install_gh_issue_workflow.sh
└── README.md
```

The root README will link to the module. A root compatibility wrapper may dispatch to the module installer if the target-repository argument convention remains unambiguous.

### Target Repository Layout

Installation produces this layout in each target repository:

```text
<target-repo>/
├── .agents/
│   ├── skills/
│   │   ├── gh-plan-to-issues/
│   │   ├── gh-sync-issues/
│   │   ├── gh-work-queue/
│   │   └── _shared/
│   └── gh-issue-workflow/
│       └── config.json
├── .claude/
│   ├── skills -> ../.agents/skills
│   └── agents/
├── .codex/
│   ├── skills -> ../.agents/skills
│   └── agents/
└── .github/
    ├── ISSUE_TEMPLATE/
    │   ├── parent_issue.yml
    │   └── sub_issue.yml
    └── pull_request_template.md
```

`.agents/skills` is the canonical installed copy shared by both agent hosts. Existing repository files outside the managed skill and agent paths remain untouched.

### Workflow Data Flow

The existing high-level protocol remains intact:

```text
Markdown plan
  → plan atoms and executable work items
  → validated bundle.json
  → independent bundle review
  → approved-bundle.json
  → GitHub parent/work issues and dependency reconciliation
  → ready-task queue
  → implementation and configured validation
  → optional specification review, then code review
  → PR creation
  → explicitly requested merge and issue closure
```

Existing bundle markers, including `PLAN_ROLE`, `PLAN_KEY`, `PLAN_RUN`, `PLAN_ITEM`, and `CHANGE_ID`, remain compatible. Run IDs continue to derive from bundle content, with the existing timestamp disambiguation behavior where required. Existing state migration is not needed because `sw` remains independent; compatibility is preserved to avoid changing the meaning of bundles and archives in future adopters.

## Repository Configuration

Each target repository owns `.agents/gh-issue-workflow/config.json`. Configuration is versioned with the repository and is never overwritten by skill upgrades.

### Precedence

Values are resolved in this order:

1. explicit CLI arguments;
2. the target repository's `config.json`;
3. built-in generic defaults.

There are no hidden `sw`-specific defaults. The generic defaults use `Feature` and `Task`, the bundled template paths, and repository-root-relative output paths. A repository that wants the source workflow's OpenSpec behavior selects it explicitly.

### Configuration Domains

| Domain | Responsibility |
| --- | --- |
| `issue_types` | Parent and work issue type names; defaults to `Feature` and `Task`. |
| `templates` | Parent/work issue form paths and PR template path. |
| `fields` | Parent and work field-ID mappings used by validation and rendering. |
| `spec_policy` | One of `openspec`, `optional`, or `none`, plus applicable specification roots. |
| `validation` | Repository-specific environment setup and test commands. |
| `agents` | Names of preflight, bundle review, environment, implementation, specification review, code review, and merge roles. |
| `paths` | Plan, sync state, queue, review, and cache roots. |
| `pr_policy` | Branch/PR conventions, close keyword, review expectations, and merge policy. |

Configuration is loaded through a shared workflow-config component rather than parsed independently by each CLI. Unknown keys and invalid values fail validation with actionable messages. Paths must remain inside the target repository unless explicitly supplied as absolute CLI paths for local inspection.

### Specification Policies

- `openspec`: `spec_impact` is required and must refer to an allowed `openspec/specs/**/spec.md` path. Execution performs the existing specification reconciliation and strict OpenSpec validation.
- `optional`: `spec_impact` may refer to repository documentation such as `docs/**`. OpenSpec checks run only when the repository and configured specification impact actually use OpenSpec.
- `none`: `spec_impact` may be omitted. Bundle validation and issue rendering do not require it, and specification reconciliation/review is skipped explicitly rather than reported as completed.

The selected policy is recorded in the bundle so plan validation, issue rendering, and work-queue execution cannot silently apply different rules.

## Runtime Components

### Workflow Configuration and Paths

A shared runtime component resolves the Git repository root, loads and validates configuration, maps field IDs, and produces all output paths. It removes exact-directory-depth import assumptions and the need to import through `.codex/skills`.

Every relative output path is resolved from the target repository root, not the caller's current subdirectory.

### GitHub Context

Repository resolution prefers an explicit `--repo`, then current-repository detection through `gh repo view`. Cached context is keyed by both repository root and `owner/repo`; a cache entry can never replace fresh current-repository detection for another checkout.

GitHub host information comes from resolved context. Issue URL parsing accepts the detected GitHub Enterprise host as well as github.com rather than assuming one fixed hostname.

### Bundle and Approval Validation

Plan validation uses configured field mappings and the selected specification policy. Approved bundle metadata includes the canonical bundle hash and specification policy.

Before any remote mutation, sync verifies that the approved bundle still matches the current canonical bundle. A missing, stale, or altered approval stops synchronization with instructions to review the changed bundle again. This converts the previous prompt-only approval rule into an executable safeguard without changing the bundle protocol.

### Issue Synchronization

Existing create/resume behavior, content-hash run IDs, `CHANGE_ID` markers, native sub-issue reconciliation, blocked-by reconciliation, parent upsert, and supersession handling are retained. Parent/work type names and template field mappings come from configuration.

Before remote writes, preflight verifies:

- `gh` is installed and authenticated;
- resolved repository identity agrees with configuration and cached state;
- configured issue types and template fields are available;
- required native sub-issue, blocked-by, and closing-PR APIs are usable;
- approved bundle metadata matches the current bundle.

### Work Queue and Agents

Queue membership uses the configured work issue type. Readiness, open-blocker filtering, open closing-PR detection, PR body rendering, unresolved review-thread checks, and closure polling retain their existing semantics.

Generic agent roles are:

- preflight;
- bundle reviewer;
- environment/validation runner;
- implementer;
- specification reviewer where enabled;
- code reviewer;
- merge closer.

Agent definitions contain role-specific process guidance but no product imports, hardware toolchains, fixed repository paths, or fixed model selections. Build and test commands come from repository configuration. If specification review is disabled by policy, the workflow records that it was skipped by configuration.

### PR and Merge Safety

One work item continues to use one issue branch and one PR. Specification review, when enabled, precedes code review. PR rendering continues to use configured template placeholders and `Fixes #N` by default.

Merge remains explicitly opt-in. The workflow must not merge while required checks or reviews fail, while unresolved non-outdated review threads remain, or while issue closure has not reached the expected state. `--admin` and equivalent bypasses are forbidden. Failures stop for user guidance rather than triggering repeated forceful mutations.

## Installer and Upgrade Behavior

The installer is invoked from `dev-tools` with an explicit target:

```bash
bash modules/gh-issue-workflow/install/install_gh_issue_workflow.sh \
  --repo /path/to/target-repo
```

It supports `--dry-run` to print planned filesystem changes without applying them.

Installer rules:

- validate that the target is a Git repository before writing;
- copy only managed skills and generic agent definitions during installation or update;
- create `config.json` and GitHub templates only when missing;
- preserve existing repository configuration and customized GitHub templates;
- make repeated installation idempotent;
- create relative symlinks on POSIX and directory junctions on Windows for `.claude/skills` and `.codex/skills`;
- stop with remediation instructions if compatibility links cannot be created, rather than silently creating divergent copies;
- never run `git push`, create GitHub issues, or otherwise mutate remote state;
- never read source files from `sw` at install time or runtime.

An update replaces only files owned by the module. Unrelated repository-local skills and agents remain untouched.

## Dry-Run and Side-Effect Semantics

The generalized dry-run has two guarantees:

1. no remote mutation;
2. no plan archive, bundle, run state, review state, or repository-context cache writes.

Rendering and validation are performed in memory or in a temporary directory that is removed before exit. Formal synchronization alone creates persistent archives and run state. These rules apply consistently to plan rendering and sync dry-runs.

Errors are reported with the repository, operation, and failed precondition. A failed operation must not print a success summary or advance task state.

## Testing Strategy

### Offline Tests

Port the existing 17 offline tests into the module and remove their dependency on `sw`, its `uv` environment, and compatibility-symlink imports. The tests must run using `dev-tools`' documented Python test entry point plus explicitly documented module dependencies.

Add focused coverage for:

1. all three specification policies in bundle validation and issue rendering;
2. configurable issue type names, field IDs, and template paths;
3. cache isolation across repositories and checkouts;
4. github.com and GitHub Enterprise issue URL parsing;
5. dry-run absence of remote and persistent local side effects;
6. rejection of missing, stale, or altered approved bundles;
7. repository-root path resolution from arbitrary subdirectories;
8. installation, idempotent update, configuration preservation, and dry-run in temporary repositories;
9. explicit failure when required compatibility links cannot be created;
10. synchronization and dependency reconciliation against a mock `gh` executable;
11. queue readiness and PR rendering using configured issue types and templates;
12. installer refusal of a non-Git target and attempts to overwrite existing configuration.

Tests do not contact `sw` or real GitHub services. Filesystem fixtures use temporary Git repositories.

### Optional Integration Tests

Live GitHub integration is opt-in and separate from the normal suite. It requires an explicitly named disposable test repository and credentials supplied by the user. It is not part of first-version acceptance and can never default to `sw`.

### Documentation

The module README documents prerequisites, installation, configuration, specification policies, update behavior, and uninstall guidance. Module documentation also covers the bundle/approval contract, run-state layout, field mappings, dry-run guarantees, and troubleshooting.

The root README lists the module and its installer without duplicating the full guide.

## Acceptance Criteria

The first version is complete when all offline tests pass and two isolated fixture repositories demonstrate the following without reading `sw` scripts or changing real GitHub data:

- a repository with `spec_policy: none` completes install, plan validation, bundle rendering, dry-run sync rendering, mock synchronization, queue readiness, and PR body rendering without `spec_impact`;
- a repository with `spec_policy: openspec` completes the same flow with required OpenSpec impacts and strict local specification validation;
- both installations preserve repository-local configuration on upgrade;
- repository context, generated state, and cache files remain isolated between the two fixtures;
- no test or installation step pushes commits or mutates a real GitHub repository.

## Future Evolution

If multiple adopters require materially different bundle schemas or orchestration behavior, the configuration overlay can evolve into explicit core-engine policy adapters. A standalone versioned Python package with thin skill wrappers remains a later distribution option, not a first-version requirement.
