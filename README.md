# dev-tools

A modular collection of personal development tools, installable helper scripts, templates, and agent skills for Linux, WSL, and Windows.

The root of this repo is a catalog. Each substantial helper owns its implementation and detailed docs under `modules/`.

## Modules

| Module | Purpose |
| --- | --- |
| [`modules/api-switcher`](modules/api-switcher/README.md) | `cc_api` and `codex_api` provider switchers, provider templates, and merge helpers |
| [`modules/docx-reader`](modules/docx-reader/README.md) | Codex skill and script for safe `.docx` text extraction |
| [`modules/zotero-bridge`](modules/zotero-bridge/README.md) | Codex skill and script for read-only Zotero Desktop collection manifests |
| [`modules/proxy`](modules/proxy/README.md) | `proxy` executable and shell wrapper installer |
| [`modules/shell-startup-normalizer`](modules/shell-startup-normalizer/README.md) | Codex and Claude Code skill for reorganizing shell startup files |
| [`modules/vim-setup`](modules/vim-setup/README.md) | Claude Code skill for restoring a preferred Vim setup |
| [`modules/oh-my--paper`](modules/oh-my--paper/README.md) | Submodule-backed paper reading project with its own docs |

## Layout

```text
bin/        compatibility wrappers for helper executables
install/    compatibility wrappers for installers
modules/    canonical helper modules and module docs
shared/     utilities shared across modules
docs/       cross-repo guides
tests/      repo-local verification scripts
```

## Quick install

Run only the installers you want. Root install scripts are compatibility wrappers that dispatch to the canonical module installers.

```bash
bash install/install_codex_api.sh
bash install/install_cc_api.sh
bash install/install_proxy.sh
bash install/install_codex_docx_reader_skill.sh
bash install/install_codex_zotero_bridge_skill.sh
bash install/install_codex_shell_startup_skill.sh
bash install/install_claude_shell_startup_skill.sh
bash install/install_claude_vim_setup_skill.sh
```

Windows native PowerShell installers are available for the API switchers:

```powershell
.\install\install_codex_api_windows.ps1
.\install\install_cc_api_windows.ps1
```

## Prerequisites

- `~/.codex/` must already exist before installing `codex_api`.
- `~/.claude/` must already exist before installing `cc_api`.
- `python3` is required on Linux/WSL; `python` is required on Windows.
- `proxy` is most useful when `~/.bashrc` sources `~/.bash_functions`.

## Secrets and templates

This repo stores sanitized placeholders only. After first-time installation, fill in real secrets in:

- `~/.codex/auth_list.json`
- `~/.claude/provider_list.json`

Re-running API switcher installers adds new template entries without overwriting existing secrets.

## Cross-repo docs

- [Permission migration](docs/permission-migration.md)
- [Submodule maintenance](docs/submodules.md)
- [npm troubleshooting](docs/npm-troubleshooting.md)

## Verification

```bash
python3 -m unittest discover -s tests -v
```
