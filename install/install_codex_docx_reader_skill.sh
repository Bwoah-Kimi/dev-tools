#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
exec bash "${REPO_ROOT}/modules/docx-reader/install/install_codex_docx_reader_skill.sh" "$@"
