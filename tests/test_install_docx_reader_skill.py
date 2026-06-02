import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCX_READER_INSTALL = "modules/docx-reader/install"


def bash_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if len(value) >= 3 and value[1:3] == ":/":
        return f"/mnt/{value[0].lower()}/{value[3:]}"
    return value


def run_bash_with_home(script: str, home: Path) -> subprocess.CompletedProcess:
    command = f"HOME={shlex.quote(bash_path(home))} bash {shlex.quote(script)}"
    return subprocess.run(
        ["bash", "-lc", command],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


class InstallDocxReaderSkillTest(unittest.TestCase):
    def test_install_codex_docx_reader_skill(self):
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            home = Path(tmp)
            result = run_bash_with_home(
                f"{DOCX_READER_INSTALL}/install_codex_docx_reader_skill.sh",
                home,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            target = home / ".codex" / "skills" / "docx-reader"
            self.assertTrue((target / "SKILL.md").exists())
            self.assertTrue((target / "scripts" / "read_docx.py").exists())


if __name__ == "__main__":
    unittest.main()
