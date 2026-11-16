# gh-issue-workflow

Repository-local, configuration-driven GitHub Issue workflow skills: turn an
implementation plan into reviewed issues, synchronize them to GitHub with
parent/work issue types and native Blocked-by dependencies, and drive work
through implementation, validation, review, PR creation, and opt-in merge.

The module is generic. Repository policy — issue types, form fields,
specification handling, validation commands, agent roles, and PR rules —
lives in each target repository's own profile, not in this engine.

## Prerequisites

- Git and Python 3.12+
- GitHub CLI (`gh`) installed and authenticated with `repo` scope
- PyYAML (issue form loading) and pytest for the offline test suite
- The target repository must support GitHub Issue Types, native sub-issues,
  and native Blocked-by relationships

## Lifecycle

```bash
# 1. Install managed skills and agent definitions (no profile yet)
bash modules/gh-issue-workflow/install/install_gh_issue_workflow.sh install \
  --repo /path/to/target-repo

# 2. Initialize the repository profile (agent-led, confirmed)
#    Invoke the gh-workflow-init skill in /path/to/target-repo.

# 3. Check configuration (local only; add --github for read-only remote checks)
bash modules/gh-issue-workflow/install/install_gh_issue_workflow.sh doctor \
  --repo /path/to/target-repo

# 4. Update managed files while preserving the repository profile
bash modules/gh-issue-workflow/install/install_gh_issue_workflow.sh update \
  --repo /path/to/target-repo
```

Every filesystem command supports `--dry-run`.

`install` copies only managed skills and generic agent definitions, then
creates `.claude/skills` and `.codex/skills` links (symlinks on POSIX,
directory junctions on Windows) to the shared `.agents/skills` tree. It never
creates `config.json`, `project-context.md`, or GitHub templates, never pushes,
and never creates remote data. If a link cannot be created it stops with
remediation instructions instead of leaving divergent copies.

`init` is deliberately agent-led. Repository discovery, conflict resolution,
and policy confirmation need judgment; the `gh-workflow-init` skill performs
read-only discovery, confirms every decision, and previews all writes before
applying them.

`update` refuses to overwrite a managed file that changed locally since the
last install (hash manifest) and never touches repository-owned files:
`config.json`, `project-context.md`, GitHub templates, and unrelated local
skills and agents.

## Repository profile

`.agents/gh-issue-workflow/config.json` holds executable settings:
`issue_types`, `templates`, `fields`, `spec_policy`, `validation`, `agents`,
`paths`, and `pr_policy`. `.agents/gh-issue-workflow/project-context.md`
records required documents, constraints, and validation evidence expectations,
referencing normative documents instead of duplicating them.

Resolution order: explicit CLI arguments → repository `config.json` → generic
defaults (see `templates/config.json`). Output paths must stay inside the
repository.

### Specification policies

| Mode | Behavior |
| --- | --- |
| `openspec` | `spec_impact` required; paths must match `openspec/specs/**/spec.md`; execution reconciles canonical specs and runs strict OpenSpec validation. |
| `optional` | `spec_impact` required; paths may be configured documentation roots; OpenSpec checks run only for actual OpenSpec impacts. |
| `none` | `spec_impact` may be omitted; rendering omits the section; spec review is recorded as skipped by policy — never claimed as performed. |

The selected policy is recorded in the bundle approval so validation,
rendering, and execution cannot silently disagree.

## Daily workflow

1. `gh-plan-to-issues` — author and structurally validate a bundle, render a
   dry-run preview, obtain independent bundle review, then record the approved
   hash and policy:

   ```bash
   python3 .agents/skills/_shared/approval.py write \
     --bundle out/gh-plan-to-issues/<plan_key>/bundle.json \
     --approved-bundle out/gh-plan-to-issues/<plan_key>/review/approved-bundle.json \
     --spec-mode <configured-mode>
   ```

2. `gh-sync-issues` — live sync. Requires the approval record; a missing,
   stale, or altered approval (hash, content, or policy mismatch) stops the
   sync before any cache, archive, state, or remote write.

3. `gh-work-queue` — inspect the configured work queue, render PR bodies with
   the configured close keyword, drive execution, and run configured
   validation commands. Merge is opt-in only; `--admin` and bypassing required
   checks or unresolved non-outdated review threads are forbidden.

### Dry-run guarantees

`--dry-run` performs no remote mutation and writes no plan archive, bundle,
run state, review state, or context cache. Repository-context caching is keyed
by repository root and `owner/repo`; a cached context can never override
current-repository detection for another checkout. GitHub Enterprise hosts are
supported for issue URL parsing.

## Offline tests

```bash
python -m pip install -r modules/gh-issue-workflow/requirements-dev.txt
python -m pytest modules/gh-issue-workflow/tests -q
```

The suite covers both fixture profiles end to end — a repository without
OpenSpec and one with strict OpenSpec — through install, confirmed init, local
doctor, plan validation, dry-run rendering, approval, mock synchronization,
queue readiness, and PR rendering. All GitHub interaction runs against the
fake `gh` in `tests/fixtures/`; no test contacts a real repository. Live
GitHub integration tests are not part of this suite and require an explicitly
named disposable repository.

## Uninstall

Remove `.agents/skills/{gh-workflow-init,gh-plan-to-issues,gh-sync-issues,gh-work-queue,_shared}`,
`.agents/gh-issue-workflow/managed-files.json`, the managed files under
`.claude/agents` and `.codex/agents`, and the `.claude/skills` /
`.codex/skills` links. Keep `config.json` and `project-context.md` if you plan
to reinstall; they are repository-owned.
