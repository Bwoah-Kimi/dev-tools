# Disable Claude-Mem Without Uninstalling It

## Objective

Disable `claude-mem` globally for Claude Code and Codex while retaining the
installed plugin, marketplace registration, cached package, database, logs,
and previously captured memories. The change must be reversible.

## Current State

- `claude-mem@thedotmack` is installed at user scope and enabled in Claude
  Code.
- `~/.claude-mem/transcript-watch.json` contains an active `codex` watch for
  `~/.codex/sessions/**/*.jsonl`.
- The Codex watch has injected a `<claude-mem-context>` block into
  `/root/dev-tools/AGENTS.md`. No other such workspace context files were
  found under `/root`.
- No live claude-mem worker process is currently present.

## Design

### Claude Code

Use Claude Code's native user-scope plugin disable operation for
`claude-mem@thedotmack`. This changes its enabled state to `false` without
removing its entry from the installed-plugin registry or deleting its cache.

### Codex

Remove only the active `codex` watch from
`~/.claude-mem/transcript-watch.json`. The Codex schema and all claude-mem
data remain in place, but no Codex transcript can be observed or used to
inject context. There is no supported `enabled: false` field for individual
watches, so removing the watch is the smallest persistent disable operation.

### Existing Injected Context

Remove only content delimited by `<claude-mem-context>` and
`</claude-mem-context>` from affected `AGENTS.md` files. Preserve any unrelated
instructions. If the generated block is the entire untracked file, remove the
now-empty file.

### Runtime

Stop an existing transcript watcher only if one is running. No process action
is needed when the recorded worker state is stale, as it is currently.

## Preservation Guarantees

The change must not remove or alter:

- the `claude-mem` plugin installation or marketplace registration;
- the repository's `modules/claude-mem` submodule;
- `~/.claude-mem/claude-mem.db`, logs, or backups;
- unrelated Claude Code settings;
- unrelated `AGENTS.md` content; or
- pre-existing user worktree changes.

## Verification

After implementation:

1. `claude plugin list` reports `claude-mem@thedotmack` as disabled.
2. Claude settings record the plugin as disabled while the installed-plugin
   registry still contains it.
3. The transcript watch configuration has no active watch named `codex`.
4. No `AGENTS.md` under `/root` contains a `<claude-mem-context>` block.
5. The plugin cache and claude-mem database still exist.
6. Existing unrelated worktree changes remain unchanged.

## Re-enabling

Re-enable the user-scope Claude Code plugin with Claude's native plugin enable
command. Re-register the Codex transcript watch with claude-mem's Codex
integration installer. Existing retained data can then be used again.
