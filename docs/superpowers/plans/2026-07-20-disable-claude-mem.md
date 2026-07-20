# Disable Claude-Mem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistently disable claude-mem for user-scope Claude Code and Codex while preserving the installed plugin and all stored data.

**Architecture:** Use Claude Code's native plugin state for Claude Code, and remove the executable `codex` watch from claude-mem's transcript-watch configuration because that schema has no per-watch disabled flag. Remove the already-generated context block separately so stale instructions cannot remain active.

**Tech Stack:** Claude Code plugin CLI, JSON configuration with `jq`, Codex `AGENTS.md`, shell verification

---

### Task 1: Verify Preconditions and Preservation Baseline

**Files:**
- Read: `/root/.claude/settings.json`
- Read: `/root/.claude/plugins/installed_plugins.json`
- Read: `/root/.claude-mem/transcript-watch.json`
- Read: `/root/dev-tools/AGENTS.md`

- [ ] **Step 1: Record unrelated repository state**

Run: `git status --short`

Expected: `modules/oh-my--paper` remains modified; no existing user change is staged or altered.

- [ ] **Step 2: Verify the Claude Code plugin starts enabled and installed**

Run: `jq -e '.enabledPlugins["claude-mem@thedotmack"] == true' /root/.claude/settings.json`

Expected: exit 0 without printing any settings or credentials.

Run: `jq -e '.plugins["claude-mem@thedotmack"] | length > 0' /root/.claude/plugins/installed_plugins.json`

Expected: exit 0.

- [ ] **Step 3: Verify the Codex watch starts active**

Run: `jq -e 'any(.watches[]; .name == "codex")' /root/.claude-mem/transcript-watch.json`

Expected: `true` and exit 0.

- [ ] **Step 4: Verify the generated context file is claude-mem-only**

Run: `rg -n '^<claude-mem-context>$|^</claude-mem-context>$' /root/dev-tools/AGENTS.md`

Expected: exactly one opening and one closing tag. Inspect the file before deletion and stop if unrelated instructions exist outside the tagged block.

### Task 2: Disable the Claude Code Plugin

**Files:**
- Modify through CLI: `/root/.claude/settings.json`
- Preserve: `/root/.claude/plugins/installed_plugins.json`

- [ ] **Step 1: Apply the native user-scope disable operation**

Run: `claude plugin disable claude-mem@thedotmack --scope user`

Expected: command succeeds and reports the plugin disabled. This may require permission to write the user-level Claude configuration.

- [ ] **Step 2: Verify disabled state**

Run: `jq -e '.enabledPlugins["claude-mem@thedotmack"] == false' /root/.claude/settings.json`

Expected: exit 0.

Run: `claude plugin list`

Expected: `claude-mem@thedotmack` remains listed at user scope with status `disabled`.

- [ ] **Step 3: Verify installation was preserved**

Run: `jq -e '.plugins["claude-mem@thedotmack"] | length > 0' /root/.claude/plugins/installed_plugins.json`

Expected: exit 0.

### Task 3: Disable the Codex Transcript Watch

**Files:**
- Modify: `/root/.claude-mem/transcript-watch.json`
- Create temporarily: `/tmp/claude-mem-transcript-watch.disabled.json`

- [ ] **Step 1: Produce a minimal transformed configuration**

Run: `jq '.watches |= map(select(.name != "codex"))' /root/.claude-mem/transcript-watch.json > /tmp/claude-mem-transcript-watch.disabled.json`

Expected: the temporary file is valid JSON, contains no watch named `codex`, and retains the existing schemas and state-file setting.

- [ ] **Step 2: Validate the transformed configuration before installation**

Run: `jq -e '([.watches[] | select(.name == "codex")] | length) == 0 and (.schemas.codex != null)' /tmp/claude-mem-transcript-watch.disabled.json`

Expected: `true` and exit 0.

- [ ] **Step 3: Install the transformed configuration**

Run: `cp /tmp/claude-mem-transcript-watch.disabled.json /root/.claude-mem/transcript-watch.json`

Expected: copy succeeds while retaining the existing destination file and claude-mem data directory. This requires permission to write the user-level claude-mem configuration.

- [ ] **Step 4: Verify the watch is persistently inactive**

Run: `jq -e '([.watches[] | select(.name == "codex")] | length) == 0' /root/.claude-mem/transcript-watch.json`

Expected: `true` and exit 0.

Run: `ps -ef | rg '[c]laude-mem|[t]ranscript-watch|[w]orker-service'`

Expected: no active claude-mem runtime. If one appears, run
`npx claude-mem stop`, then repeat the process check.

### Task 4: Remove Stale Codex Context

**Files:**
- Delete if generated-only: `/root/dev-tools/AGENTS.md`

- [ ] **Step 1: Remove the generated-only context file**

Delete `/root/dev-tools/AGENTS.md` with `apply_patch` only after Task 1 confirms that the tagged claude-mem block is its entire content. If unrelated content is present, use `apply_patch` to remove only the tagged block.

- [ ] **Step 2: Verify no injected context remains**

Run: `rg -uuu -l --glob 'AGENTS.md' '<claude-mem-context>' /root 2>/dev/null`

Expected: no output and exit 1.

### Task 5: Run Final Preservation Checks

**Files:**
- Read: `/root/.claude/settings.json`
- Read: `/root/.claude/plugins/installed_plugins.json`
- Read: `/root/.claude/plugins/known_marketplaces.json`
- Read: `/root/.claude-mem/transcript-watch.json`
- Verify existence: `/root/.claude/plugins/cache/thedotmack/claude-mem/12.6.5`
- Verify existence: `/root/.claude-mem/claude-mem.db`

- [ ] **Step 1: Check all disabled-state assertions together**

Run each command independently:

```bash
jq -e '.enabledPlugins["claude-mem@thedotmack"] == false' /root/.claude/settings.json
jq -e '.plugins["claude-mem@thedotmack"] | length > 0' /root/.claude/plugins/installed_plugins.json
jq -e '.thedotmack != null' /root/.claude/plugins/known_marketplaces.json
jq -e '([.watches[] | select(.name == "codex")] | length) == 0' /root/.claude-mem/transcript-watch.json
test -d /root/.claude/plugins/cache/thedotmack/claude-mem/12.6.5
test -f /root/.claude-mem/claude-mem.db
```

Expected: every command exits 0.

- [ ] **Step 2: Confirm the repository worktree was preserved**

Run: `git status --short`

Expected: the pre-existing `modules/oh-my--paper` modification is unchanged, the generated `AGENTS.md` is absent, and no unrelated file is modified.

- [ ] **Step 3: Report the reversible result**

Report that Claude Code and Codex integration entry points are disabled, that the plugin and data remain installed, and that re-enabling requires the native Claude plugin enable command plus re-registering the Codex watch.
