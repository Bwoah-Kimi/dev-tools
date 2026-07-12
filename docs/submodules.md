# Submodule modules

Large projects that this repo owns but maintains as separate repositories should live under `modules/` as git submodules.

Examples:

```text
modules/oh-my--paper/
modules/claude-mem/
```

Each submodule owns its own implementation, README, docs, and tests. The root repo owns only the module catalog, optional wrapper glue, and the pinned submodule commit.

## Clone and initialize

```bash
git submodule update --init --recursive
```

## Check current submodule pins

```bash
git submodule status
```

A leading `+` means the checked-out submodule commit differs from the commit currently pinned by the root repo.

## Update an owned submodule

```bash
git -C modules/oh-my--paper fetch
git -C modules/oh-my--paper checkout main
git -C modules/oh-my--paper pull --ff-only
git add modules/oh-my--paper
git commit -m "Update Oh-my--paper submodule"
```

Use the corresponding module path for other submodules, such as
`modules/claude-mem` or `modules/llm-wiki-skill`.

For `llm-wiki-skill`, update the submodule first and then refresh the Codex
installation from the root wrapper:

```powershell
git -C modules/llm-wiki-skill pull --ff-only
powershell -ExecutionPolicy Bypass -File .\install\install_codex_llm_wiki_skill.ps1
git add modules/llm-wiki-skill
```

The submodule is the source of truth. `$CODEX_HOME/skills/llm-wiki` is an
installed copy and should not be edited directly.

## Add a new owned submodule

```bash
git submodule add <repo-url> modules/<module-name>
git commit -m "Add <module-name> submodule"
```

Prefer lowercase directory names under `modules/`, even if the upstream repository uses different capitalization.

## Local wrappers

Only add wrapper scripts or local docs outside the submodule when `dev-tools` needs repo-specific glue. Do not duplicate the submodule's own README or internal documentation in the root repo.
