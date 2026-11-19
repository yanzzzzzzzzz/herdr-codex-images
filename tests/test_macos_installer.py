"""File-preservation and rollback integration tests. No GUI/core/model is started."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "darwin", "macOS installer integration")
class MacInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        root = Path(cls.build.name)
        source = root / "fixture.c"
        source.write_text('#include <stdio.h>\nint main(void) { puts("herdr-app 0.1.16"); return 0; }\n')
        cls.native = root / "Herdr"
        subprocess.run(["xcrun", "clang", str(source), "-o", str(cls.native)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hci-installer-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home with spaces"
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home))
        for key in ("ZDOTDIR", "HERDR_APP_HOME", "HC_TERMINAL_ID"):
            self.env.pop(key, None)
        self.root = self.home / ".local/share/herdr-codex-images"
        self.original = self.home / ".config/herdr-app"
        self.original.mkdir(parents=True)
        (self.original / "settings.json").write_text('{"zoom":1.25}')
        (self.original / "view.json").write_text('{"spaces":["keep-my-project"]}')
        self.project = self.home / "Documents/my-project/source.txt"
        self.project.parent.mkdir(parents=True)
        self.project.write_text("unfinished user work\n")
        self.profile = self.home / ".zshrc"
        self.profile.write_text("# custom user profile\nexport KEEP_ME=yes\n")
        self.baseline = {p: p.read_bytes() for p in (self.project, self.profile, self.original / "settings.json", self.original / "view.json")}

    def package(self, version="v0.1.0-test.1", unsafe=False):
        work = Path(self.temp.name) / version
        payload = work / "payload"
        app = payload / "Herdr Images.app/Contents"
        (app / "MacOS").mkdir(parents=True)
        shutil.copy2(self.native, app / "MacOS/Herdr")
        (app / "Info.plist").write_bytes(plistlib.dumps({
            "CFBundleExecutable": "Herdr", "CFBundleIdentifier": "io.github.hci.test",
            "CFBundlePackageType": "APPL", "CFBundleVersion": "1",
        }))
        subprocess.run(["codesign", "--force", "--sign", "-", str(app.parent)], check=True, capture_output=True)
        for name, content in {
            "codex/bin/codex": '#!/bin/sh\necho "codex-cli 0.169.1"\n',
            "codex/codex-path/rg": '#!/bin/sh\necho "ripgrep test"\n',
            "core/bin/hc": '#!/bin/sh\necho "hc 0.1.21"\n',
        }.items():
            path = payload / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            path.chmod(0o755)
        (payload / "bin").mkdir()
        shutil.copy2(REPO / "tools/herdr-images.sh", payload / "bin/herdr-images")
        (payload / "bin/herdr-images").chmod(0o755)
        (payload / "VERSION").write_text(version + "\n")
        (payload / "macos-entitlements.plist").write_bytes(plistlib.dumps({"com.apple.security.cs.allow-jit": True}))
        entries = sorted(p for p in payload.rglob("*") if p.is_file())
        (payload / "FILES.sha256").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(payload)}\n" for p in entries))
        asset = work / f"herdr-codex-images-{version}-macos-arm64.tar.gz"
        with tarfile.open(asset, "w:gz") as archive:
            archive.add(payload, arcname="payload")
            if unsafe:
                archive.add(self.project, arcname="../must-not-extract")
        sums = work / "SHA256SUMS"
        sums.write_text(f"{hashlib.sha256(asset.read_bytes()).hexdigest()}  {asset.name}\n")
        return version, asset, sums

    def install(self, package, success=True):
        version, asset, sums = package
        result = subprocess.run(["sh", str(REPO / "install.sh"), "--version", version,
                                 "--archive", str(asset), "--checksums", str(sums), "--no-open"],
                                env=self.env, text=True, capture_output=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def manage(self, command, success=True):
        result = subprocess.run([str(self.home / ".local/bin/herdr-images"), command], env=self.env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def assert_user_files_preserved(self, include_profile=False):
        for path, content in self.baseline.items():
            if path != self.profile or include_profile:
                self.assertEqual(path.read_bytes(), content, str(path))

    def test_legacy_update_fails_before_network_or_execution(self):
        self.install(self.package())
        result = self.manage('update', success=False)
        self.assertIn('retired', result.stdout + result.stderr)
        self.assert_user_files_preserved()

    def test_install_preserves_projects_and_original_settings(self):
        self.install(self.package())
        self.assert_user_files_preserved()
        self.assertEqual((self.root / "app-home/view.json").read_bytes(), self.baseline[self.original / "view.json"])
        self.assertIn(self.baseline[self.profile].decode(), self.profile.read_text())
        self.manage("doctor")

    def test_repeat_install_and_uninstall_preserve_intervening_edits(self):
        package = self.package()
        self.install(package)
        self.install(package)
        self.assertEqual(self.profile.read_text().count("# BEGIN herdr-codex-images-installer"), 1)
        with self.profile.open("a") as out:
            out.write("# user edit after install\n")
        self.manage("uninstall")
        self.assertEqual(self.profile.read_text(), self.baseline[self.profile].decode() + "# user edit after install\n")
        self.assertTrue((self.root / "app-home/view.json").exists())
        self.assertFalse((self.home / "Applications/Herdr Images.app").is_symlink())
        self.assert_user_files_preserved()

    def test_update_and_rollback_do_not_replace_user_settings(self):
        self.install(self.package())
        (self.root / "app-home/settings.json").write_text('{"zoom":1.75}')
        self.install(self.package("v0.1.0-test.2"))
        self.assertEqual(os.readlink(self.root / "current"), "versions/v0.1.0-test.2")
        self.manage("rollback")
        self.assertEqual(os.readlink(self.root / "current"), "versions/v0.1.0-test.1")
        self.assertEqual((self.root / "app-home/settings.json").read_text(), '{"zoom":1.75}')
        self.manage("doctor")
        self.assert_user_files_preserved()

    def test_corrupt_download_does_not_activate_or_edit_profile(self):
        package = self.package()
        package[2].write_text("0" * 64 + "  " + package[1].name + "\n")
        self.install(package, success=False)
        self.assertFalse((self.root / "current").exists())
        self.assert_user_files_preserved(include_profile=True)

    def test_path_traversal_is_rejected(self):
        self.install(self.package(unsafe=True), success=False)
        self.assert_user_files_preserved(include_profile=True)
        self.assertFalse((self.root / "must-not-extract").exists())

    def test_existing_unmanaged_app_is_not_overwritten(self):
        app = self.home / "Applications/Herdr Images.app"
        app.mkdir(parents=True)
        (app / "keep").write_text("unmanaged app")
        self.install(self.package(), success=False)
        self.assertEqual((app / "keep").read_text(), "unmanaged app")
        self.assert_user_files_preserved(include_profile=True)

    def test_modified_installed_binary_is_detected(self):
        package = self.package()
        self.install(package)
        (self.root / "current/codex/bin/codex").write_text("#!/bin/sh\nexit 0\n")
        self.manage("doctor", success=False)
        self.install(package, success=False)

    def test_malformed_profile_block_is_preserved(self):
        self.profile.write_text("# BEGIN herdr-codex-images-installer\n# unfinished\n")
        self.baseline[self.profile] = self.profile.read_bytes()
        self.install(self.package(), success=False)
        self.assertFalse((self.root / "current").exists())
        self.assert_user_files_preserved(include_profile=True)

    def test_dotfiles_symlink_is_preserved(self):
        target = self.home / "dotfiles/zshrc"
        target.parent.mkdir()
        self.profile.rename(target)
        self.profile.symlink_to("dotfiles/zshrc")
        self.install(self.package())
        self.assertTrue(self.profile.is_symlink())
        self.manage("uninstall")
        self.assertTrue(self.profile.is_symlink())
        self.assertEqual(target.read_bytes(), self.baseline[self.profile])


if __name__ == "__main__":
    unittest.main()
