#!/usr/bin/env python3
from __future__ import annotations
import json
import re
import sys
from pathlib import Path


SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
MODEL_PROVIDER_RE = re.compile(
    r'(?m)^model_provider\s*=\s*"(?P<provider>[^"]*)"\s*$'
)
KEY_VALUE_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*=\s*(.+)\s*$")


def fail(message: str) -> "None":
    print(message, file=sys.stderr)
    raise SystemExit(1)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"failed to read {path}: {exc}")


def parse_toml_scalar(raw_value: str, *, path: Path, line_number: int) -> object:
    if raw_value in {"true", "false"}:
        return raw_value == "true"
    if raw_value.startswith('"') and raw_value.endswith('"'):
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError as exc:
            fail(f"malformed TOML string in {path}:{line_number}: {exc}")
    fail(f"unsupported TOML value in {path}:{line_number}: {raw_value}")


def load_provider_config(path: Path) -> tuple[str, dict[str, dict[str, object]]]:
    text = read_text(path)
    model_provider = ""
    providers: dict[str, dict[str, object]] = {}
    current_provider: str | None = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        section_match = SECTION_RE.match(line)
        if section_match:
            section_name = section_match.group(1)
            if section_name.startswith("model_providers."):
                current_provider = section_name[len("model_providers.") :]
                if not current_provider:
                    fail(f"malformed provider section in {path}:{line_number}")
                providers[current_provider] = {}
            else:
                current_provider = None
            continue

        key_value_match = KEY_VALUE_RE.match(line)
        if not key_value_match:
            fail(f"malformed TOML line in {path}:{line_number}: {line}")

        key, raw_value = key_value_match.groups()
        value = parse_toml_scalar(raw_value, path=path, line_number=line_number)

        if current_provider is not None:
            providers[current_provider][key] = value
            continue
        if key == "model_provider":
            if not isinstance(value, str) or not value:
                fail(f"invalid model_provider in {path}:{line_number}")
            model_provider = value

    if not model_provider:
        fail(f"missing model_provider in {path}")
    if not providers:
        fail(f"missing model_providers in {path}")
    return model_provider, providers


def render_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    fail(f"unsupported TOML value type: {type(value).__name__}")


def render_provider_blocks(providers: dict[str, dict[str, object]]) -> str:
    blocks: list[str] = []
    for provider_name, provider_config in providers.items():
        block_lines = [f"[model_providers.{provider_name}]"]
        for key, value in provider_config.items():
            block_lines.append(f"{key} = {render_toml_value(value)}")
        blocks.append("\n".join(block_lines))
    return "\n\n".join(blocks).rstrip("\n")


def strip_provider_sections(text: str) -> str:
    kept_lines: list[str] = []
    skipping = False

    for line in text.splitlines(keepends=True):
        match = SECTION_RE.match(line.strip())
        if match:
            section_name = match.group(1)
            if section_name.startswith("model_providers."):
                skipping = True
                continue
            skipping = False
        if skipping:
            continue
        kept_lines.append(line)
    return "".join(kept_lines)


def replace_model_provider(text: str, provider_name: str) -> str:
    updated, count = MODEL_PROVIDER_RE.subn(
        f'model_provider = "{provider_name}"',
        text,
        count=1,
    )
    if count == 1:
        return updated
    return f'model_provider = "{provider_name}"\n{updated}'


def get_model_provider(text: str) -> str:
    match = MODEL_PROVIDER_RE.search(text)
    return match.group("provider") if match else ""


def insert_provider_blocks(text: str, provider_blocks: str) -> str:
    lines = text.splitlines(keepends=True)
    first_section_index = len(lines)
    for index, line in enumerate(lines):
        if SECTION_RE.match(line.strip()):
            first_section_index = index
            break

    prefix = "".join(lines[:first_section_index]).strip("\n")
    suffix = "".join(lines[first_section_index:]).strip("\n")

    parts = [part for part in (prefix, provider_blocks.strip("\n"), suffix) if part]
    return "\n\n".join(parts) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        fail("usage: merge_codex_config.py <local-config> <provider-config>")

    local_path = Path(argv[0])
    provider_path = Path(argv[1])

    local_text = read_text(local_path)
    default_provider, providers = load_provider_config(provider_path)
    current_provider = get_model_provider(local_text)
    provider_name = current_provider if current_provider in providers else default_provider

    without_provider_sections = strip_provider_sections(local_text)
    with_provider_name = replace_model_provider(without_provider_sections, provider_name)
    provider_blocks = render_provider_blocks(providers)
    merged_text = insert_provider_blocks(with_provider_name, provider_blocks)
    local_path.write_text(merged_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
