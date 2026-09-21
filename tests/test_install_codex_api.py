import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_SWITCHER = REPO_ROOT / "modules" / "api-switcher"
API_SWITCHER_INSTALL = "modules/api-switcher/install"


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


class InstallCodexApiTest(unittest.TestCase):
    def test_install_codex_api_copies_script_and_merges_config(self):
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            home = Path(tmp)
            (home / ".codex").mkdir()
            (home / ".codex" / "config.toml").write_text(
                'model_provider = "old-provider"\n'
                'model = "gpt-5.4"\n'
                '\n'
                '[projects."/tmp/project"]\n'
                'trust_level = "trusted"\n',
                encoding="utf-8",
            )

            result = run_bash_with_home(f"{API_SWITCHER_INSTALL}/install_codex_api.sh", home)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((home / ".local" / "bin" / "codex_api").exists())
            auth_list = json.loads((home / ".codex" / "auth_list.json").read_text(encoding="utf-8"))
            self.assertEqual(auth_list["PACIFIC-Lab"], "<fill-me>")
            self.assertEqual(auth_list["packycode"], "<fill-me>")
            self.assertEqual(auth_list["codex-for-me-main"], "<fill-me>")
            config = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn('model_provider = "micu"', config)
            self.assertIn('[projects."/tmp/project"]', config)
            self.assertIn('trust_level = "trusted"', config)
            self.assertIn('[model_providers.PACIFIC-Lab]', config)
            self.assertIn('[model_providers.cubence]', config)
            self.assertIn('[model_providers.codex-for-me-bk2]', config)


if __name__ == "__main__":
    unittest.main()
