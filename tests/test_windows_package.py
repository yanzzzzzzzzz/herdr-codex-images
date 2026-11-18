"""Reject mismatched official Codex resources before creating a release archive."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.name == "nt", "Windows packaging")
class WindowsPackageTests(unittest.TestCase):
    def test_mismatched_codex_companions_are_rejected_before_packaging(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "official"
            bundle.mkdir()
            (bundle / "codex-package.json").write_text(json.dumps({
                "version": "0.169.0", "target": "x86_64-pc-windows-msvc"
            }))
            output = root / "release"
            args = [sys.executable, str(repo / "tools/package_windows.py")]
            for name in ("herdr-dir", "herdr-binary", "codex-binary", "core-dir", "crt-dir"):
                args += ["--" + name, str(root / "unused")]
            args += ["--codex-dir", str(bundle), "--output", str(output)]
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("official Windows x64 0.169.1 bundle", result.stderr)
            self.assertFalse(output.exists())
