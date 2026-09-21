# api-switcher

Provider switchers for Claude Code and Codex.

## Contents

```text
bin/        cc_api, codex_api, and Windows .bat launchers
install/    Linux/WSL and Windows installers
lib/        JSON and Codex TOML merge helpers
templates/  sanitized provider, auth, and permission templates
```

## Prerequisites

**Linux / WSL**

- `~/.claude/` must already exist before running `install_cc_api.sh`.
- `~/.codex/` must already exist before running `install_codex_api.sh`.
- `python3` must be available.

**Windows**

- `%USERPROFILE%\.claude\` must already exist before running `install_cc_api_windows.ps1`.
- `%USERPROFILE%\.codex\` must already exist before running `install_codex_api_windows.ps1`.
- `python` must be available on `PATH`.

## Install

Canonical module installers:

```bash
bash modules/api-switcher/install/install_cc_api.sh
bash modules/api-switcher/install/install_codex_api.sh
```

Root compatibility wrappers are also available:

```bash
bash install/install_cc_api.sh
bash install/install_codex_api.sh
```

Windows:

```powershell
.\modules\api-switcher\install\install_cc_api_windows.ps1
.\modules\api-switcher\install\install_codex_api_windows.ps1
```

or through root wrappers:

```powershell
.\install\install_cc_api_windows.ps1
.\install\install_codex_api_windows.ps1
```

Windows installers copy both the Python script and a `.bat` launcher to `%USERPROFILE%\.local\bin\`. Add that directory to your `PATH` if it is not already there.

## What the installers do

### `install_cc_api`

- copies `bin/cc_api` to `~/.local/bin/cc_api` and `cc_api.bat` on Windows
- merges `templates/claude/provider_list.json` into `~/.claude/provider_list.json`
- preserves existing provider entries and tokens
- leaves `~/.claude/settings.json` untouched

### `install_codex_api`

- copies `bin/codex_api` to `~/.local/bin/codex_api` and `codex_api.bat` on Windows
- merges `templates/codex/auth_list.json` into `~/.codex/auth_list.json`
- preserves existing API keys
- merges helper-managed provider config from `templates/codex/config.providers.toml` into `~/.codex/config.toml`
- preserves the active provider when it still exists in the provider template
- preserves unrelated local Codex config, including project trust settings

## Usage

```bash
cc_api -l, --list              # list available Claude Code providers
cc_api -c, --current           # show active provider
cc_api -s, --switch <provider> # switch to a provider

codex_api -l, --list              # list available Codex providers
codex_api -c, --current           # show active provider
codex_api -s, --switch <provider> # switch to a provider

codex_api --sync-history [provider]             # assign all history to a provider
codex_api --sync-history [provider] --dry-run   # preview a history migration
codex_api --switch <provider> --sync-history    # migrate history, then switch
codex_api --history-backups                     # list migration backups
codex_api --restore-history <backup-id>         # restore provider assignments
codex_api --delete-history [backup-id|all]      # delete migration backups
```

## Codex history migration

Codex records a session's provider in both the session JSONL metadata and the
SQLite thread index. `--sync-history` updates both so the normal `codex resume`
picker and Codex clients such as the VS Code extension can see the sessions
under the target provider. If the provider is omitted, the active provider in
`config.toml` is used.

Close Codex CLI sessions and the VS Code Codex extension before a migration.
The command refuses to continue when it detects an active session or cannot
acquire the SQLite write transaction.

Before changing history, the tool writes a small provider-assignment manifest
under `~/.codex/history-provider-backups/`. It does not copy conversation
contents. `--restore-history` restores assignments from a manifest and creates
a new manifest for the pre-restore state. `--delete-history` with no argument,
or with `all`, deletes every manifest; it never deletes or changes a Codex
conversation and does not undo a completed migration.

History migration validates the known JSONL and SQLite fields before writing.
Unsupported or compressed session formats cause it to stop without making a
best-effort partial conversion.

## Manual follow-up

The repo intentionally does not store real API keys or private tokens.

After first-time installation, fill in real secrets in:

- `~/.codex/auth_list.json` — one key per Codex provider alias
- `~/.claude/provider_list.json` — env vars per Claude Code provider

Re-running an installer after adding new providers to the templates adds the new entries without touching your existing keys.

If multiple Codex provider aliases share the same upstream API key, repeat that key under each alias in `~/.codex/auth_list.json`.

## Permission templates

Curated approval rules live in:

- `templates/claude/settings.json`
- `templates/codex/default.rules`

See [`../../docs/permission-migration.md`](../../docs/permission-migration.md) for how to apply them without overwriting credentials.
