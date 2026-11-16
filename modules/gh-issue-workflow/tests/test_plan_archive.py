from __future__ import annotations

from pathlib import Path

import pytest

import file_archive as fa  # noqa: E402


def test_archive_file_copies_and_verifies_sha256(tmp_path: Path) -> None:
    source_path = tmp_path / "source.md"
    source_path.write_text("hello\n", encoding="utf-8")
    expected_sha = fa.sha256_file(source_path)

    dest_path = tmp_path / "runs" / "r1" / "plan.md"
    archived_path = fa.archive_file(
        source_path=source_path,
        dest_path=dest_path,
        expected_sha256=expected_sha,
    )

    assert archived_path == dest_path
    assert dest_path.read_text(encoding="utf-8") == "hello\n"
    assert fa.sha256_file(dest_path) == expected_sha


def test_archive_file_raises_on_sha_mismatch(tmp_path: Path) -> None:
    source_path = tmp_path / "source.md"
    source_path.write_text("hello\n", encoding="utf-8")

    dest_path = tmp_path / "runs" / "r1" / "plan.md"
    with pytest.raises(fa.FileArchiveError, match=r"SHA-256 mismatch"):
        fa.archive_file(
            source_path=source_path,
            dest_path=dest_path,
            expected_sha256="0" * 64,
        )
