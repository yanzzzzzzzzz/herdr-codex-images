import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "patch_component.py"
SPEC = importlib.util.spec_from_file_location("patch_component", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PatchComponentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="image-patch-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout = self.root / "upstream"
        self.checkout.mkdir()
        self.run_git("init", "--quiet")
        self.run_git("config", "user.name", "Fixture")
        self.run_git("config", "user.email", "fixture@example.invalid")
        (self.checkout / "sample.txt").write_bytes(b"before\n")
        self.run_git("add", "sample.txt")
        self.run_git("commit", "--quiet", "-m", "fixture")
        self.commit = self.run_git("rev-parse", "HEAD").strip()
        self.package = self.root / "package"
        self.package.mkdir()
        self.patch = self.package / "change.patch"
        self.patch.write_bytes(
            b"diff --git a/sample.txt b/sample.txt\n"
            b"--- a/sample.txt\n+++ b/sample.txt\n@@ -1 +1 @@\n-before\n+after\n"
        )
        self.manifest = {
            "schema": 1,
            "components": {"herdr": {
                "commit": self.commit, "patch": "change.patch",
                "sha256": hashlib.sha256(self.patch.read_bytes()).hexdigest(),
            }},
        }
        self.save_manifest()

    def run_git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.checkout), *args], check=True,
            capture_output=True, text=True, encoding="utf-8",
        ).stdout

    def save_manifest(self):
        (self.package / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def invoke(self, **kwargs):
        return module.patch_component("herdr", self.checkout, root=self.package, **kwargs)

    def test_check_does_not_mutate_and_apply_is_repeatable(self):
        self.assertIn("applicable", self.invoke())
        self.assertEqual((self.checkout / "sample.txt").read_bytes(), b"before\n")
        self.assertIn("Patch applied", self.invoke(apply=True))
        self.assertEqual((self.checkout / "sample.txt").read_bytes(), b"after\n")
        self.assertIn("already applied", self.invoke(apply=True))

    def test_wrong_base_is_rejected(self):
        self.manifest["components"]["herdr"]["commit"] = "0" * 40
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Wrong upstream commit"):
            self.invoke(apply=True)

    def test_tampered_patch_is_rejected_before_mutation(self):
        self.patch.write_bytes(self.patch.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.invoke(apply=True)
        self.assertEqual((self.checkout / "sample.txt").read_bytes(), b"before\n")

    def test_dirty_checkout_is_preserved(self):
        (self.checkout / "unrelated.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not clean"):
            self.invoke(apply=True)
        self.assertEqual((self.checkout / "sample.txt").read_bytes(), b"before\n")
        self.assertEqual((self.checkout / "unrelated.txt").read_text(), "keep")

    def test_manifest_cannot_escape_package(self):
        self.manifest["components"]["herdr"]["patch"] = "../outside.patch"
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "inside the package"):
            module.load_manifest(self.package)


if __name__ == "__main__":
    unittest.main()
