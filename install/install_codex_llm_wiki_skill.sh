#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTALLER="${REPO_ROOT}/modules/llm-wiki-skill/install.sh"

if [ ! -f "${INSTALLER}" ]; then
  printf 'llm-wiki submodule is not initialized: %s\n' "${INSTALLER}" >&2
  printf 'Run: git submodule update --init --recursive\n' >&2
  exit 1
fi

bash "${INSTALLER}" --platform codex "$@"

for arg in "$@"; do
  if [ "$arg" = "--dry-run" ]; then
    exit 0
  fi
done

CODEX_SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/llm-wiki"
printf '%s\n' "${REPO_ROOT}/modules/llm-wiki-skill" > "${CODEX_SKILL_DIR}/.llm-wiki-source"
printf 'Recorded managed source: %s\n' "${REPO_ROOT}/modules/llm-wiki-skill"
