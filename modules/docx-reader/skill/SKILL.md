---
name: docx-reader
description: Use when Codex needs to read, inspect, search, summarize, extract text from, or convert Microsoft Word .docx files without corrupt text or binary output.
---

# DOCX Reader

## Core Rule

Never inspect `.docx` files with plain-text commands such as `cat`, `type`, `Get-Content`, or `rg` directly. A `.docx` is a ZIP package containing XML and related resources, not a text file.

## Default Workflow

Use the bundled extractor first:

```bash
python scripts/read_docx.py path/to/file.docx
```

When running from outside this skill directory, use the installed script path:

```bash
python ~/.codex/skills/docx-reader/scripts/read_docx.py path/to/file.docx
```

The script extracts paragraphs and table rows as UTF-8 text using Python standard library APIs only.

## Fallbacks

If the bundled script fails:

- report the exact error before trying another method
- use `python-docx` when installed and plain text is enough
- use `pandoc input.docx -t markdown` when available and markdown structure is useful
- unzip the `.docx` and parse `word/document.xml` with an XML parser

Use the Documents skill or plugin when the task depends on layout, comments, tracked changes, headers, footers, images, or visual fidelity.

## Common Mistakes

| Mistake | Fix |
| --- | --- |
| Running `Get-Content file.docx` | Use the extractor script. |
| Searching `.docx` with `rg` directly | Extract text first, then search the extracted text. |
| Assuming garbled output is an encoding issue | Treat the file as OOXML inside ZIP. |
| Using this skill for visual review | Use the Documents plugin instead. |
