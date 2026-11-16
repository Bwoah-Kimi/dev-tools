#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${MODULE_ROOT}/../.." && pwd)"
source "${REPO_ROOT}/shared/install_common.sh"
PYTHON_BIN="$(find_python)"
exec "${PYTHON_BIN}" "${SCRIPT_DIR}/gh_issue_workflow.py" "$@"
