import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CODEX_API = REPO_ROOT / "modules" / "api-switcher" / "bin" / "codex_api"


def write_config(codex_home: Path, active_provider: str = "provider-a") -> None:
    (codex_home / "config.toml").write_text(
        f'model_provider = "{active_provider}"\n'
        '\n'
        '[model_providers.provider-a]\n'
        'name = "provider-a"\n'
        'base_url = "https://a.example/v1"\n'
        'wire_api = "responses"\n'
        'requires_openai_auth = true\n'
        '\n'
        '[model_providers.provider-b]\n'
        'name = "provider-b"\n'
        'base_url = "https://b.example/v1"\n'
        'wire_api = "responses"\n'
        'requires_openai_auth = true\n',
        encoding="utf-8",
    )
    (codex_home / "auth_list.json").write_text(
        json.dumps({"provider-a": "key-a", "provider-b": "key-b"}),
        encoding="utf-8",
    )
    (codex_home / "auth.json").write_text(
        json.dumps({"OPENAI_API_KEY": "key-a"}), encoding="utf-8"
    )


def create_state_db(codex_home: Path, threads: list[tuple[str, str, str]]) -> None:
    connection = sqlite3.connect(codex_home / "state_5.sqlite")
    connection.execute(
        "CREATE TABLE threads ("
        "id TEXT PRIMARY KEY, rollout_path TEXT NOT NULL, model_provider TEXT NOT NULL"
        ")"
    )
    connection.executemany(
        "INSERT INTO threads (id, rollout_path, model_provider) VALUES (?, ?, ?)",
        threads,
    )
    connection.commit()
    connection.close()


def create_session(
    codex_home: Path, thread_id: str, provider: str, *, archived: bool = False
) -> Path:
    root = "archived_sessions" if archived else "sessions"
    path = codex_home / root / "2026" / "08" / "16" / f"rollout-{thread_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "timestamp": "2026-08-16T00:00:00Z",
        "type": "session_meta",
        "payload": {
            "id": thread_id,
            "cwd": "/tmp/project",
            "model_provider": provider,
        },
    }
    path.write_text(
        json.dumps(metadata, separators=(",", ":"))
        + "\n"
        + '{"type":"response_item","payload":{"message":"keep me unchanged"}}\n',
        encoding="utf-8",
    )
    return path


def read_session_provider(path: Path) -> str:
    with path.open(encoding="utf-8") as handle:
        return json.loads(handle.readline())["payload"]["model_provider"]


def read_database_providers(codex_home: Path) -> dict[str, str]:
    connection = sqlite3.connect(codex_home / "state_5.sqlite")
    providers = dict(connection.execute("SELECT id, model_provider FROM threads"))
    connection.close()
    return providers


class CodexApiHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(dir=REPO_ROOT)
        self.codex_home = Path(self.temporary_directory.name) / ".codex"
        self.codex_home.mkdir()
        write_config(self.codex_home)
        self.session_a = create_session(
            self.codex_home, "thread-a", "provider-a"
        )
        self.session_b = create_session(
            self.codex_home, "thread-b", "provider-b", archived=True
        )
        create_state_db(
            self.codex_home,
            [
                ("thread-a", str(self.session_a), "provider-a"),
                ("thread-b", str(self.session_b), "provider-b"),
            ],
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def run_api(self, *arguments: str) -> subprocess.CompletedProcess:
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(self.codex_home)
        return subprocess.run(
            [str(CODEX_API), *arguments],
            cwd=REPO_ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_sync_history_updates_jsonl_and_database_and_creates_manifest(self):
        body_before = self.session_b.read_bytes().split(b"\n", 1)[1]

        result = self.run_api("--sync-history", "provider-a")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_session_provider(self.session_a), "provider-a")
        self.assertEqual(read_session_provider(self.session_b), "provider-a")
        self.assertEqual(
            read_database_providers(self.codex_home),
            {"thread-a": "provider-a", "thread-b": "provider-a"},
        )
        self.assertEqual(self.session_b.read_bytes().split(b"\n", 1)[1], body_before)
        manifests = list(
            (self.codex_home / "history-provider-backups").glob("*.json")
        )
        self.assertEqual(len(manifests), 1)
        manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["sessions"][0]["provider"], "provider-b")

    def test_dry_run_does_not_change_history_or_create_backup(self):
        result = self.run_api("--sync-history", "provider-a", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_session_provider(self.session_b), "provider-b")
        self.assertEqual(
            read_database_providers(self.codex_home)["thread-b"], "provider-b"
        )
        self.assertFalse(
            (self.codex_home / "history-provider-backups").exists()
        )

    def test_restore_history_restores_manifest_state(self):
        sync_result = self.run_api("--sync-history", "provider-a")
        backup_id = sync_result.stdout.strip().splitlines()[-1].split(": ", 1)[1]

        result = self.run_api("--restore-history", backup_id)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_session_provider(self.session_b), "provider-b")
        self.assertEqual(
            read_database_providers(self.codex_home)["thread-b"], "provider-b"
        )
        self.assertEqual(
            len(list((self.codex_home / "history-provider-backups").glob("*.json"))),
            2,
        )

    def test_delete_history_without_argument_deletes_all_manifests_only(self):
        self.assertEqual(
            self.run_api("--sync-history", "provider-a").returncode, 0
        )

        result = self.run_api("--delete-history")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            list((self.codex_home / "history-provider-backups").glob("*.json")), []
        )
        self.assertTrue(self.session_a.exists())
        self.assertTrue(self.session_b.exists())
        self.assertEqual(read_session_provider(self.session_b), "provider-a")

    def test_switch_with_sync_uses_target_provider_for_both(self):
        result = self.run_api("--switch", "provider-b", "--sync-history")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_session_provider(self.session_a), "provider-b")
        self.assertEqual(
            set(read_database_providers(self.codex_home).values()), {"provider-b"}
        )
        self.assertIn(
            'model_provider = "provider-b"',
            (self.codex_home / "config.toml").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            json.loads((self.codex_home / "auth.json").read_text(encoding="utf-8")),
            {"OPENAI_API_KEY": "key-b"},
        )


if __name__ == "__main__":
    unittest.main()
