#!/usr/bin/env python3
"""Extract readable text from a .docx file without third-party dependencies."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree


W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocxReadError(Exception):
    """Expected user-facing DOCX extraction failure."""


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def text_from_node(node: ElementTree.Element) -> str:
    parts: list[str] = []
    for child in node.iter():
        name = local_name(child.tag)
        if name == "t" and child.text:
            parts.append(child.text)
        elif name == "tab":
            parts.append("\t")
        elif name in {"br", "cr"}:
            parts.append("\n")
    return "".join(parts)


def child_elements(node: ElementTree.Element, name: str) -> Iterable[ElementTree.Element]:
    for child in node:
        if local_name(child.tag) == name:
            yield child


def table_rows(table: ElementTree.Element) -> Iterable[str]:
    for row in child_elements(table, "tr"):
        cells: list[str] = []
        for cell in child_elements(row, "tc"):
            paragraphs = [
                normalize_text(text_from_node(paragraph))
                for paragraph in child_elements(cell, "p")
            ]
            cells.append(" ".join(text for text in paragraphs if text))
        line = "\t".join(cells).strip()
        if line:
            yield line


def document_lines(root: ElementTree.Element) -> Iterable[str]:
    body = root.find(f"{W_NS}body")
    if body is None:
        raise DocxReadError("word/document.xml has no document body")

    for block in body:
        name = local_name(block.tag)
        if name == "p":
            line = normalize_text(text_from_node(block))
            if line:
                yield line
        elif name == "tbl":
            yield from table_rows(block)


def normalize_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        parts = [" ".join(part.split()) for part in line.split("\t")]
        normalized = "\t".join(parts).strip()
        if normalized:
            lines.append(normalized)
    return "\n".join(line for line in lines if line).strip()


def extract_docx(path: Path) -> list[str]:
    if path.suffix.lower() != ".docx":
        raise DocxReadError(f"expected a .docx file, got: {path}")
    if not path.exists():
        raise DocxReadError(f"file not found: {path}")
    if not path.is_file():
        raise DocxReadError(f"not a file: {path}")

    try:
        with zipfile.ZipFile(path) as archive:
            try:
                xml_bytes = archive.read("word/document.xml")
            except KeyError as exc:
                raise DocxReadError("missing word/document.xml in .docx package") from exc
    except zipfile.BadZipFile as exc:
        raise DocxReadError(f"not a valid .docx ZIP package: {path}") from exc

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise DocxReadError(f"failed to parse word/document.xml: {exc}") from exc

    return list(document_lines(root))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract paragraphs and table rows from a .docx file as UTF-8 text.",
    )
    parser.add_argument("docx", type=Path, help="Path to a .docx file")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        lines = extract_docx(args.docx)
    except DocxReadError as exc:
        print(f"read_docx.py: {exc}", file=sys.stderr)
        return 1

    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
