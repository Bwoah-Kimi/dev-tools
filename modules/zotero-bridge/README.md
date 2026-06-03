# zotero-bridge

Codex skill and helper script for reading Zotero Desktop collections through the
local Zotero API and exporting research-direction manifests for downstream
workflows such as llm-wiki ingestion.

Zotero remains the source of truth. This module reads collections, items, and
PDF attachment paths from the local API; it does not modify the Zotero library
or copy PDF files.

## Install

```bash
bash modules/zotero-bridge/install/install_codex_zotero_bridge_skill.sh
```

Root compatibility wrapper:

```bash
bash install/install_codex_zotero_bridge_skill.sh
```

## Zotero Setup

Open Zotero Desktop and enable:

```text
Settings -> Advanced -> Allow other applications on this computer to communicate with Zotero
```

## Quick Checks

```bash
python modules/zotero-bridge/skill/scripts/zotero_bridge.py status
python modules/zotero-bridge/skill/scripts/zotero_bridge.py list-collections
python modules/zotero-bridge/skill/scripts/zotero_bridge.py export-manifest "Thermal Management & Prediction" --wiki-root D:/research-wikis/thermal
```
