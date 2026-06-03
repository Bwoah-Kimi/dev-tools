import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "modules" / "zotero-bridge" / "skill" / "scripts" / "zotero_bridge.py"

spec = importlib.util.spec_from_file_location("zotero_bridge", SCRIPT)
zotero_bridge = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(zotero_bridge)


class ZoteroBridgeScriptTest(unittest.TestCase):
    def test_file_url_to_path_decodes_windows_paths(self):
        path = zotero_bridge.file_url_to_path("file:///D:/Zhu%20Zhantong/Zotero/storage/ABC/paper.pdf")

        self.assertIsNotNone(path)
        self.assertIn("Zhu Zhantong", path)
        self.assertTrue(path.endswith(str(Path("Zotero") / "storage" / "ABC" / "paper.pdf")))

    def test_collection_tree_renders_nested_collections(self):
        collections = [
            {
                "key": "ROOT",
                "meta": {"numItems": 1, "numCollections": 1},
                "data": {"name": "Research", "parentCollection": False},
            },
            {
                "key": "CHILD",
                "meta": {"numItems": 2, "numCollections": 0},
                "data": {"name": "Thermal", "parentCollection": "ROOT"},
            },
        ]

        output = zotero_bridge.render_collection_tree(collections)

        self.assertIn("- Research [ROOT] items=1 children=1", output)
        self.assertIn("  - Thermal [CHILD] items=2 children=0", output)

    def test_export_manifest_records_pdf_attachments(self):
        collections = [
            {
                "key": "COLL",
                "meta": {"numItems": 1, "numCollections": 0},
                "data": {"name": "Thermal", "parentCollection": False},
            }
        ]
        paper = {
            "key": "ITEM1",
            "meta": {"parsedDate": "2025-04-08", "numChildren": 1},
            "data": {
                "itemType": "journalArticle",
                "title": "Thermal Paper",
                "date": "2025",
                "DOI": "10/example",
                "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
                "collections": ["COLL"],
            },
        }
        attachment = {
            "key": "ATT1",
            "links": {
                "enclosure": {
                    "href": "file:///D:/Zotero/storage/ATT1/paper.pdf",
                    "type": "application/pdf",
                    "title": "paper.pdf",
                }
            },
            "data": {
                "itemType": "attachment",
                "title": "PDF",
                "contentType": "application/pdf",
                "filename": "paper.pdf",
            },
        }

        def fake_paged_request(_api_base, endpoint, _params=None):
            if endpoint == "/users/0/collections":
                return collections
            if endpoint == "/users/0/collections/COLL/items":
                return [paper]
            if endpoint == "/users/0/items/ITEM1/children":
                return [attachment]
            return []

        with mock.patch.object(zotero_bridge, "paged_request", side_effect=fake_paged_request):
            manifest = zotero_bridge.export_manifest("http://example/api", "Thermal", "wiki-root", recursive=False)

        self.assertEqual(manifest["summary"]["item_count"], 1)
        self.assertEqual(manifest["summary"]["items_with_pdf"], 1)
        self.assertEqual(manifest["items"][0]["item_key"], "ITEM1")
        self.assertEqual(manifest["items"][0]["pdf_attachments"][0]["attachment_key"], "ATT1")

    def test_cli_export_writes_manifest(self):
        manifest = {
            "collection": {"key": "COLL"},
            "summary": {"item_count": 1, "items_with_pdf": 1, "items_missing_pdf": 0},
        }
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            output = Path(tmp) / "manifest.json"
            with mock.patch.object(zotero_bridge, "export_manifest", return_value=manifest):
                result = zotero_bridge.main(
                    ["export-manifest", "Thermal", "--wiki-root", tmp, "--output", str(output)]
                )

            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["collection"]["key"], "COLL")


if __name__ == "__main__":
    unittest.main()
