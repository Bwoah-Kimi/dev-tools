import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "modules" / "docx-reader" / "skill" / "scripts" / "read_docx.py"


def write_minimal_docx(path: Path) -> None:
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Hello</w:t></w:r>
      <w:r><w:tab/></w:r>
      <w:r><w:t>world</w:t></w:r>
    </w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Cell A</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Cell B</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", document_xml)


class DocxReaderScriptTest(unittest.TestCase):
    def test_extracts_paragraphs_and_tables_from_docx(self):
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            docx_path = Path(tmp) / "sample.docx"
            write_minimal_docx(docx_path)

            result = subprocess.run(
                ["python", str(SCRIPT), str(docx_path)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Hello\tworld", result.stdout)
            self.assertIn("Cell A\tCell B", result.stdout)

    def test_rejects_non_docx_input_with_clear_error(self):
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            text_path = Path(tmp) / "not-docx.txt"
            text_path.write_text("plain text", encoding="utf-8")

            result = subprocess.run(
                ["python", str(SCRIPT), str(text_path)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("expected a .docx file", result.stderr)


if __name__ == "__main__":
    unittest.main()
