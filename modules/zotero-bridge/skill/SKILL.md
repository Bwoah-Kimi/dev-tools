---
name: zotero-bridge
description: Use when reading, listing, syncing, or exporting Zotero Desktop collections, papers, PDF attachments, notes, or annotations for downstream workflows such as llm-wiki ingestion, literature review, paper analysis, or research knowledge-base updates without duplicating the Zotero library.
---

# Zotero Bridge

## Purpose

Use Zotero as the source of truth for papers, collections, metadata, PDFs, notes,
and annotations. This skill bridges Zotero Desktop to downstream workflows such
as llm-wiki without exporting the whole library or copying Zotero storage.

## Safety Rules

- Treat Zotero as read-only unless the user explicitly asks for a write action.
- Do not copy PDF files by default. Pass local Zotero attachment paths to the
  downstream workflow instead.
- Use Zotero item keys and attachment keys as stable identifiers. Local PDF paths
  can differ across devices and should be refreshed from Zotero when needed.
- Scope work to the user-named collection or item. Do not scan unrelated
  collections when a specific research direction is given.

## Prerequisite

Zotero Desktop must be running with local API access enabled:

```text
Settings -> Advanced -> Allow other applications on this computer to communicate with Zotero
```

The default local API base is:

```text
http://127.0.0.1:23119/api
```

## Helper Script

Use the bundled script for deterministic Zotero API access:

```bash
python scripts/zotero_bridge.py status
python scripts/zotero_bridge.py list-collections
python scripts/zotero_bridge.py export-manifest "Collection Name" --wiki-root path/to/wiki
```

When running from outside this skill directory after installation:

```bash
python ~/.codex/skills/zotero-bridge/scripts/zotero_bridge.py list-collections
```

## Workflows

### List Collections

Run:

```bash
python scripts/zotero_bridge.py list-collections
```

Use this before asking the user to pick a research direction.

### Export a Collection Manifest

Run:

```bash
python scripts/zotero_bridge.py export-manifest "Thermal Management & Prediction" --wiki-root D:/research-wikis/thermal
```

The manifest records collection metadata, Zotero item keys, paper metadata, PDF
attachment keys, and current-device PDF paths. It is safe to commit or reuse
after checking whether local absolute paths should stay private.

### Sync Toward llm-wiki

For llm-wiki ingestion, use the manifest as the bridge artifact:

1. Export or refresh the Zotero manifest for the selected collection.
2. Identify items with `pdf_attachments`.
3. Skip items already represented in the wiki manifest or source pages.
4. Ask llm-wiki to ingest the selected PDF paths.
5. Preserve Zotero keys in the generated wiki source metadata when possible.

## Failure Handling

- If the API returns `Local API is not enabled`, tell the user to enable the
  Zotero local API setting.
- If a collection name is ambiguous, list matching names with their keys and ask
  the user to choose one.
- If an item has no PDF attachment, keep it in the manifest with
  `pdf_attachments: []` and report it as missing PDF.
- If a PDF path is unavailable on this device, refresh from Zotero after sync or
  ask the user to open Zotero and let file sync complete.
