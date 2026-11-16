---
name: gh-workflow-init
description: "Use when initializing or reconfiguring gh-issue-workflow for a repository, including repository discovery, specification policy, validation commands, agent roles, Issue forms, and PR constraints."
---

# GitHub Issue Workflow Initialization

Adapt the generic workflow to the current repository. Initialization is agent-led: shell heuristics may locate files, but they cannot decide project policy without user confirmation.

## Preconditions

- Run from the target Git repository after `install_gh_issue_workflow.sh install --repo PATH` completes.
- Do not read another repository's profile as this repository's policy.
- Initialization creates no GitHub issue or PR and performs no push.

## 1. Read-only discovery

Inspect, when present:

- `AGENTS.md`, `CLAUDE.md`, README, and contribution guides;
- build/test manifests and documented quality gates;
- `.github/ISSUE_TEMPLATE/` and `.github/pull_request_template.md`;
- `openspec/config.yaml` and `openspec/specs/`;
- existing `.agents`, `.claude`, and `.codex` configuration;
- branch, review, merge, and release documentation.

Record evidence as `path:line` for every detected convention. Separate `detected`, `inferred`, and `unknown`; never convert an inference into a confirmed rule silently.

## 2. Confirm policy with the user

Ask one focused question at a time when evidence is absent or contradictory. Confirm:

- parent/work Issue Types and template field mappings;
- `spec_policy`: `openspec`, `optional`, or `none`;
- required setup and validation commands;
- required documents, protected areas, compatibility constraints, and PR evidence;
- agent role mappings and output paths;
- branch/review/merge rules, including the close keyword and opt-in merge.

Do not impose another repository's build system, model selection, or specification layout.

## 3. Preview the repository profile

Build a JSON answers document containing only confirmed settings. Include `required_documents` and `constraints` for `project-context.md`; these keys are consumed as context and are not written as unknown config keys.

Preview the target paths without writing:

```bash
python3 .agents/skills/gh-workflow-init/scripts/gh_workflow_profile.py --repo . --answers /path/to/confirmed-answers.json --dry-run
```

Present the proposed `config.json`, `project-context.md`, and every template creation/edit as a diff. Reference existing normative documents rather than copying their rule bodies.

## 4. Apply confirmed profile and template changes

After explicit approval, write the profile:

```bash
python3 .agents/skills/gh-workflow-init/scripts/gh_workflow_profile.py --repo . --answers /path/to/confirmed-answers.json --confirmed
```

If a profile already exists, first show the current-versus-proposed diff, obtain approval for that exact change set, then add `--reviewed-change-set`.

Templates:

- No existing templates: copy the generic templates to the configured `.github` paths after confirmation.
- Existing compatible templates: preserve them and record field mappings in config.
- Existing incompatible templates: show missing fields and proposed focused edits; edit only after confirmation.
- For `spec_policy: none`, do not require `spec_impact` in the work form. Preserve the field when the user wants optional manual use, but runtime rendering still omits it when absent from the bundle.

## 5. Validate initialization

Run local doctor and show its findings:

```bash
bash modules/gh-issue-workflow/install/install_gh_issue_workflow.sh doctor --repo /path/to/target-repo
```

When running from an installed target rather than the `dev-tools` checkout, use the module's installed doctor helper:

```bash
python3 .agents/skills/gh-workflow-init/scripts/gh_workflow_doctor.py --repo .
```

Do not run `doctor --github` unless the user wants read-only GitHub checks. Report the profile paths and any remaining manual GitHub setup. Do not create remote data to prove initialization.
