import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prepare_windows_codex import prepare_migrations


class WindowsMigrationSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sql = self.root / "codex-rs/state/migrations"
        self.sql.mkdir(parents=True)
        self.first = self.sql / "0001_threads.sql"
        self.second = self.sql / "0002_more.sql"
        self.first.write_bytes(b"CREATE TABLE threads(id TEXT);\n")
        self.second.write_bytes(b"ALTER TABLE threads ADD COLUMN title TEXT;\n")
        self.git("init", "-q")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("add", ".")
        self.git("commit", "-qm", "Canonical migration sources")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def test_preparation_matches_windows_checksums_without_semantic_changes(self):
        original = self.first.read_bytes()
        self.assertEqual(prepare_migrations(self.root), 2)
        self.assertEqual(self.first.read_bytes(), original)
        self.assertEqual(prepare_migrations(self.root, apply=True), 2)
        expected = original.replace(b"\n", b"\r\n")
        self.assertEqual(self.first.read_bytes(), expected)
        self.assertEqual(hashlib.sha384(self.first.read_bytes()).digest(), hashlib.sha384(expected).digest())
        self.assertEqual(prepare_migrations(self.root, apply=True), 0)

    def test_semantic_change_rejects_all_writes(self):
        original = self.first.read_bytes()
        self.second.write_bytes(b"DROP TABLE threads;\n")
        with self.assertRaisesRegex(ValueError, "semantic changes"):
            prepare_migrations(self.root, apply=True)
        self.assertEqual(self.first.read_bytes(), original)
