#!/usr/bin/env bash

print_step() {
    printf '==> %s\n' "$*"
}

ensure_dir() {
    mkdir -p "$1"
}

require_existing_dir() {
    if [[ ! -d "$1" ]]; then
        printf 'missing required directory: %s\n' "$1" >&2
        exit 1
    fi
}

backup_file() {
    local path="$1"
    local stamp=""

    if [[ ! -e "$path" ]]; then
        return 0
    fi

    stamp="$(date +%Y%m%d%H%M%S)"
    cp "$path" "${path}.bak.${stamp}"
}

backup_path() {
    local path="$1"
    local stamp=""

    if [[ ! -e "$path" ]]; then
        return 0
    fi

    stamp="$(date +%Y%m%d%H%M%S)"
    mv "$path" "${path}.bak.${stamp}"
}

copy_file() {
    cp "$1" "$2"
}

set_executable() {
    chmod 755 "$1"
}

find_python() {
    local candidates=()
    if [[ -n "${PYTHON:-}" ]]; then
        candidates+=("${PYTHON}")
    fi
    candidates+=(python3 python)
    # Windows: the Microsoft Store python/python3 stubs fail this probe, so
    # also try common real interpreter locations.
    candidates+=("${HOME}/miniconda3/python.exe" "${HOME}/anaconda3/python.exe")
    if [[ -n "${LOCALAPPDATA:-}" ]]; then
        candidates+=("${LOCALAPPDATA}"/Programs/Python/Python3*/python.exe)
    fi

    local candidate
    for candidate in "${candidates[@]}"; do
        # Skip unexpanded glob patterns.
        if [[ "${candidate}" == *'*'* ]]; then
            continue
        fi
        if command -v "${candidate}" >/dev/null 2>&1 && "${candidate}" -c 'import sys' >/dev/null 2>&1; then
            printf '%s\n' "${candidate}"
            return 0
        fi
    done
    printf 'missing required Python interpreter\n' >&2
    exit 1
}
