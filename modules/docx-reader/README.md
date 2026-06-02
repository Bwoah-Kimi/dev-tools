# docx-reader

Installable Codex skill for safely extracting text from Microsoft Word `.docx`
files without treating them as plain text.

## Contents

```text
skill/SKILL.md              Codex-compatible skill instructions
skill/scripts/read_docx.py  dependency-free DOCX text extractor
install/*.sh                Codex installer
```

## Install

Canonical module installer:

```bash
bash modules/docx-reader/install/install_codex_docx_reader_skill.sh
```

Root compatibility wrapper:

```bash
bash install/install_codex_docx_reader_skill.sh
```

## What the installer does

- copies `skill/` to `~/.codex/skills/docx-reader`
- backs up an existing installed skill directory before replacing it
- does not modify documents

## Usage

After installing, ask Codex to read, inspect, summarize, or search `.docx`
files with the `docx-reader` skill.

The reusable extractor can also be run directly:

```bash
python ~/.codex/skills/docx-reader/scripts/read_docx.py file.docx
```
