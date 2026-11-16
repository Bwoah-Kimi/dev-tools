# GitHub Issue Workflow Generalization Design

**Date:** 2026-11-15

## Goal

Create a reusable `gh-issue-workflow` module in `dev-tools` that generalizes the three GitHub Issue workflow skills currently maintained in the `sw` repository:

- `gh-plan-to-issues`: turn a written implementation plan into a validated, reviewable issue bundle;
- `gh-sync-issues`: synchronize an approved bundle to GitHub, including parent/sub-issue relationships and native blocked-by dependencies;
- `gh-work-queue`: inspect the task queue and drive a task through implementation, validation, review, PR creation, optional merge, and closure.

The generalized module must preserve the complete workflow while removing dependencies on the `sw` repository, its product, and its build environment. A companion `gh-workflow-init` skill adapts the generic workflow to each repository through an explicit, confirmed initialization process.

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
│   ├── gh-workflow-init/
│   │   ├── SKILL.md
│   │   └── scripts/
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
│   ├── project-context.md
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

Installation and initialization together produce this layout in each target repository:

```text
<target-repo>/
├── .agents/
│   ├── skills/
│   │   ├── gh-workflow-init/
│   │   ├── gh-plan-to-issues/
│   │   ├── gh-sync-issues/
│   │   ├── gh-work-queue/
│   │   └── _shared/
│   └── gh-issue-workflow/
│       ├── config.json
│       └── project-context.md
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

Each target repository owns `.agents/gh-issue-workflow/config.json` and `.agents/gh-issue-workflow/project-context.md`. The first contains executable workflow settings; the second records project-specific constraints and documentation navigation. Both are versioned with the repository and are never overwritten by skill upgrades.

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

## Repository Lifecycle: Install, Init, Doctor, Update

Generic files and repository adaptation are separate operations. A repository is not ready for plan synchronization merely because its skills have been copied.

```text
install → init → doctor → plan/sync/work-queue → update
```

The filesystem lifecycle commands use an explicit target repository:

```bash
bash modules/gh-issue-workflow/install/install_gh_issue_workflow.sh install \
  --repo /path/to/target-repo
bash modules/gh-issue-workflow/install/install_gh_issue_workflow.sh doctor \
  --repo /path/to/target-repo
bash modules/gh-issue-workflow/install/install_gh_issue_workflow.sh update \
  --repo /path/to/target-repo
```

Initialization is then performed by invoking the `gh-workflow-init` skill in the target repository. The shell installer deliberately has no semantic `init` subcommand: repository discovery, conflict resolution, and policy confirmation require the agent-led interview. Init uses the same shared configuration and validation helpers as the lifecycle commands.

Every filesystem command supports `--dry-run` to show proposed local changes without applying them. The init skill provides the equivalent behavior by presenting its complete proposed writes for confirmation before changing any file.

### Install

Install validates that the target is a Git repository and copies only managed skills and generic agent definitions. It creates relative symlinks on POSIX and directory junctions on Windows for `.claude/skills` and `.codex/skills`. If compatibility links cannot be created, it stops with remediation instructions rather than silently creating divergent copies.

Install does not create `config.json`, `project-context.md`, or repository GitHub templates. It is idempotent, does not modify unrelated local skills or agents, and never runs `git push` or mutates GitHub.

### Init

The `gh-workflow-init` skill performs repository onboarding in five stages.

1. **Read-only discovery.** Inspect `AGENTS.md`, `CLAUDE.md`, README/contributing guides, build and test manifests, existing Issue and PR templates, OpenSpec files, `.agents`/`.claude`/`.codex` configuration, and documented branch/PR conventions. Detection produces proposals and evidence paths, not unquestioned facts.
2. **User confirmation.** Confirm parent/work issue types and field mappings, specification policy, required validation commands, bundle acceptance information, branch/review/merge rules, and required project documents. Ask about uncertain or contradictory discoveries instead of guessing.
3. **Generate repository profile.** Write `config.json` for executable settings and `project-context.md` for project constraints, required reading, protected areas, compatibility requirements, and required validation evidence. Reference existing normative documents instead of duplicating their rules.
4. **Create or adapt templates.** Generate generic Issue/PR templates when none exist. Preserve existing templates and map their fields where possible. If required bundle fields cannot be represented, show the gaps and proposed edits; modify existing templates only after user confirmation.
5. **Preview, confirm, and validate.** Present all proposed writes before applying them. After confirmation, write the repository profile and run local doctor checks. Initialization never creates a real issue or PR.

Re-running init displays the difference between the current profile and new discovery results. Existing profile and template files are not overwritten wholesale; confirmed changes are applied as focused edits.

### Doctor

Doctor validates configuration syntax, field mappings, referenced documents, output paths, compatibility links, and configured validation commands. Its default mode is local and read-only. An explicit `--github` mode additionally checks authentication, repository identity, issue types, and required native APIs using read-only requests. It never creates or modifies GitHub data.

Doctor can be run independently after repository conventions change. Work-queue preflight uses the same validation component so initialization and daily execution cannot drift into different rule sets.

### Update

Update replaces only module-owned skills, scripts, and generic agents. It preserves `config.json`, `project-context.md`, customized GitHub templates, and unrelated repository-local files. Repeated updates are idempotent. If a new generic version requires configuration changes, update reports the required migration and stops until the user confirms it; it does not silently rewrite repository policy.

No lifecycle command reads source files from `sw`, pushes commits, or mutates remote GitHub state.

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
8. installation, idempotent update, profile preservation, and dry-run in temporary repositories;
9. init discovery, confirmed generation of `config.json` and `project-context.md`, and preservation of existing normative documents;
10. init adaptation of existing Issue/PR templates without unconfirmed overwrites;
11. local and `--github` doctor checks remaining read-only;
12. explicit failure when required compatibility links cannot be created;
13. synchronization and dependency reconciliation against a mock `gh` executable;
14. queue readiness and PR rendering using configured issue types and templates;
15. installer refusal of a non-Git target and update attempts that would overwrite repository policy.

Tests do not contact `sw` or real GitHub services. Filesystem fixtures use temporary Git repositories.

### Optional Integration Tests

Live GitHub integration is opt-in and separate from the normal suite. It requires an explicitly named disposable test repository and credentials supplied by the user. It is not part of first-version acceptance and can never default to `sw`.

### Documentation

The module README documents prerequisites, the install/init/doctor/update lifecycle, repository profiles, specification policies, update behavior, and uninstall guidance. Module documentation also covers initialization interviews and evidence paths, the bundle/approval contract, run-state layout, field mappings, dry-run guarantees, and troubleshooting.

The root README lists the module and its installer without duplicating the full guide.

## Acceptance Criteria

The first version is complete when all offline tests pass and two isolated fixture repositories demonstrate the following without reading `sw` scripts or changing real GitHub data:

- a repository with `spec_policy: none` completes install, confirmed init, local doctor, plan validation, bundle rendering, dry-run sync rendering, mock synchronization, queue readiness, and PR body rendering without `spec_impact`;
- a repository with `spec_policy: openspec` completes the same flow with required OpenSpec impacts and strict local specification validation;
- each initialized repository has a reviewed `config.json` and `project-context.md` that reference existing normative documents rather than duplicating them;
- both installations preserve repository-local profiles and customized templates on update;
- repository context, generated state, and cache files remain isolated between the two fixtures;
- no test or installation step pushes commits or mutates a real GitHub repository.

## Future Evolution

If multiple adopters require materially different bundle schemas or orchestration behavior, the configuration overlay can evolve into explicit core-engine policy adapters. A standalone versioned Python package with thin skill wrappers remains a later distribution option, not a first-version requirement.
