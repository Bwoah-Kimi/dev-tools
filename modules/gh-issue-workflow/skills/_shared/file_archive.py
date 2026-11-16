#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


class FileArchiveError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_file(
    *,
    source_path: Path,
    dest_path: Path,
    expected_sha256: str | None = None,
) -> Path:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest_path)
    archived_sha = sha256_file(dest_path)
    if expected_sha256 is not None and archived_sha != expected_sha256:
        raise FileArchiveError(
            "Archived file SHA-256 mismatch: "
            f"expected {expected_sha256}, got {archived_sha}"
        )
    return dest_path

