#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=/dev/null
source "${REPO_ROOT}/shared/install_common.sh"

HOME_DIR="${HOME:?HOME must be set}"
SKILLS_DIR="${HOME_DIR}/.claude/skills"
TARGET_DIR="${SKILLS_DIR}/ppt-master"
SOURCE_DIR="${REPO_ROOT}/modules/ppt-master/skills/ppt-master"

print_step "Installing ppt-master for Claude Code"
ensure_dir "${SKILLS_DIR}"
require_existing_dir "${SOURCE_DIR}"

backup_path "${TARGET_DIR}"
cp -R "${SOURCE_DIR}" "${TARGET_DIR}"

PYTHON_BIN="$(find_python)"
print_step "Installing Python dependencies with ${PYTHON_BIN}"
# PYTHONUTF8: pip decodes requirements.txt with the locale encoding on
# Windows (e.g. cp936), which breaks on this file's UTF-8 comments.
PYTHONUTF8=1 "${PYTHON_BIN}" -m pip install -r "${TARGET_DIR}/requirements.txt"

printf 'Installed: %s\n' "${TARGET_DIR}"
printf 'Usage: ask Claude Code to create a presentation with the ppt-master skill\n'
