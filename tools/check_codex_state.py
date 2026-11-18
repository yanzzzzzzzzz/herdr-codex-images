#!/usr/bin/env python3
"""Check Windows Codex against a synthetic existing database, never the user's data."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures"


def check_state_runtime(command):
    if isinstance(command, (str, Path)):
        command = [str(command)]
    reference = json.loads((FIXTURES / "codex-windows-state.json").read_text())
    first_sql = (FIXTURES / "codex-state-0001.sql").read_bytes().replace(b"\r\n", b"\n")
    first_checksum = hashlib.sha384(first_sql.replace(b"\n", b"\r\n")).digest()
    expected = {item["version"]: bytes.fromhex(item["sha384"]) for item in reference["migrations"]}
    if first_checksum != expected[1]:
        raise RuntimeError("Compatibility fixture checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="hci-state-compat-") as temp:
        home = Path(temp)
        database = home / reference["database"]
        with closing(sqlite3.connect(database)) as connection:
            connection.executescript(first_sql.decode("utf-8"))
            connection.execute("CREATE TABLE _sqlx_migrations (version BIGINT PRIMARY KEY, description TEXT NOT NULL, installed_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, success BOOLEAN NOT NULL, checksum BLOB NOT NULL, execution_time BIGINT NOT NULL)")
            connection.execute("INSERT INTO _sqlx_migrations (version,description,success,checksum,execution_time) VALUES (1,'threads',1,?,0)", (first_checksum,))
            connection.commit()
        env = dict(os.environ, CODEX_HOME=str(home))
        result = subprocess.run([*command, "app-server", "--listen", "stdio://"], input="", capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45, env=env)
        if result.returncode:
            raise RuntimeError("Codex cannot open an existing Windows migration fixture: " + result.stderr[-2000:])
        with closing(sqlite3.connect(database)) as connection:
            actual = dict(connection.execute("SELECT version,checksum FROM _sqlx_migrations WHERE success=1"))
        if actual != expected:
            mismatches = sorted(version for version in actual.keys() | expected.keys() if actual.get(version) != expected.get(version))
            raise RuntimeError("Windows migration checksum mismatch: " + str(mismatches))
    return {"database": reference["database"], "migration_count": len(expected), "checksum_format": "official Windows CRLF", "existing_database_fixture_passed": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    print(json.dumps(check_state_runtime(args.binary.resolve()), indent=2))
