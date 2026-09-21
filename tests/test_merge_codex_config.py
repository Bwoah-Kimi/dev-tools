import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MERGE_CODEX_CONFIG = "modules/api-switcher/lib/merge_codex_config.py"


class MergeCodexConfigTest(unittest.TestCase):
    def test_merge_replaces_only_helper_managed_codex_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            local_config = tmp_path / "config.toml"
            provider_config = tmp_path / "config.providers.toml"

            local_config.write_text(
                'model_provider = "old-provider"\n'
                'model = "gpt-5.4"\n'
                '\n'
                '[model_providers.old-provider]\n'
                'name = "old-provider"\n'
                'base_url = "https://old.example/v1"\n'
                'wire_api = "responses"\n'
                'requires_openai_auth = true\n'
                '\n'
                '[projects."/tmp/project"]\n'
                'trust_level = "trusted"\n',
                encoding="utf-8",
            )
            provider_config.write_text(
                'model_provider = "cubence"\n'
                '\n'
                '[model_providers.cubence]\n'
                'name = "cubence"\n'
                'base_url = "https://api.cubence.com/v1"\n'
                'wire_api = "responses"\n'
                'requires_openai_auth = true\n',
                encoding="utf-8",
            )

            result = subprocess.run(
                ["python", MERGE_CODEX_CONFIG, str(local_config), str(provider_config)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            merged = local_config.read_text(encoding="utf-8")
            self.assertIn('model_provider = "cubence"', merged)
            self.assertIn('model = "gpt-5.4"', merged)
            self.assertIn('[projects."/tmp/project"]', merged)
            self.assertIn('trust_level = "trusted"', merged)
            self.assertIn('[model_providers.cubence]', merged)
            self.assertNotIn('[model_providers.old-provider]', merged)

    def test_merge_preserves_active_provider_when_template_still_contains_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            local_config = tmp_path / "config.toml"
            provider_config = tmp_path / "config.providers.toml"
            local_config.write_text(
                'model_provider = "micu"\n'
                '\n'
                '[model_providers.micu]\n'
                'name = "old-micu"\n',
                encoding="utf-8",
            )
            provider_config.write_text(
                'model_provider = "codex-for-me-main"\n'
                '\n'
                '[model_providers.micu]\n'
                'name = "micu"\n'
                '\n'
                '[model_providers.codex-for-me-main]\n'
                'name = "codex-for-me-main"\n',
                encoding="utf-8",
            )

            result = subprocess.run(
                ["python", MERGE_CODEX_CONFIG, str(local_config), str(provider_config)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            merged = local_config.read_text(encoding="utf-8")
            self.assertIn('model_provider = "micu"', merged)
            self.assertIn('[model_providers.codex-for-me-main]', merged)


if __name__ == "__main__":
    unittest.main()
