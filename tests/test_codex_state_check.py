import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_codex_state import FIXTURES, check_state_runtime


class CodexStateCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.script = Path(self.temp.name) / "fake_runtime.py"
        self.script.write_text('''import json,os,sqlite3,sys
from pathlib import Path
reference=json.loads(Path(sys.argv[1]).read_text())
connection=sqlite3.connect(Path(os.environ["CODEX_HOME"])/reference["database"])
first=connection.execute("SELECT checksum FROM _sqlx_migrations WHERE version=1").fetchone()[0]
assert first==bytes.fromhex(reference["migrations"][0]["sha384"])
for item in reference["migrations"]:
 checksum=bytes.fromhex(item["sha384"])
 if "wrong" in sys.argv and item["version"]==2:checksum=bytes(48)
 connection.execute("INSERT OR REPLACE INTO _sqlx_migrations (version,description,success,checksum,execution_time) VALUES (?,'fixture',1,?,0)",(item["version"],checksum))
connection.commit()
connection.close()
''', encoding="utf-8")

    def test_verifies_all_migrations_in_isolated_home(self):
        before = os.environ.get("CODEX_HOME")
        result = check_state_runtime([sys.executable, str(self.script), str(FIXTURES / "codex-windows-state.json")])
        self.assertTrue(result["existing_database_fixture_passed"])
        self.assertEqual(result["migration_count"], 62)
        self.assertEqual(os.environ.get("CODEX_HOME"), before)

    def test_zero_exit_with_wrong_migration_checksums_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            check_state_runtime([sys.executable, str(self.script), str(FIXTURES / "codex-windows-state.json"), "wrong"])
