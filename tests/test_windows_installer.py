"""Exercise Windows PowerShell 5.1 installer against isolated files and fake tools."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]
PS = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe")


@unittest.skipUnless(os.name == "nt", "Windows installer integration")
class WindowsInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="hci-windows-fixture-")
        cls.fixture = Path(cls.build.name) / "fixture.exe"
        code = '''using System; using System.IO; using System.Reflection;
class Fixture { public static int Main(string[] args) {
string name=Path.GetFileName(Assembly.GetExecutingAssembly().Location);
if(Array.IndexOf(args,"--version")>=0) Console.WriteLine(name=="herdr-app.exe"?"herdr-app 0.1.16":name=="codex.exe"?"codex-cli 0.169.1":name=="rg.exe"?"ripgrep test":"hc 0.1.21");
if(Array.IndexOf(args,"--hold")>=0) Console.ReadLine();
return 0; } }'''
        command = "Add-Type -TypeDefinition '" + code.replace("'", "''") + "' -OutputType ConsoleApplication -OutputAssembly '" + str(cls.fixture).replace("'", "''") + "'"
        result=cls.ps(command)
        if result.returncode or not cls.fixture.exists():
            raise RuntimeError(result.stdout+result.stderr)
        cls.shortcut=Path(cls.build.name)/'windows-shortcut.dll'
        command="Add-Type -Path '"+str(REPO/'tools/windows-shortcut.cs').replace("'","''")+"' -OutputType Library -OutputAssembly '"+str(cls.shortcut).replace("'","''")+"'"
        result=cls.ps(command)
        if result.returncode or not cls.shortcut.exists():
            raise RuntimeError(result.stdout+result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    @staticmethod
    def ps(command):
        command = "$ProgressPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); " + command
        return subprocess.run([PS, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand",
                               base64.b64encode(command.encode("utf-16-le")).decode()],
                              text=True, encoding="utf-8", errors="replace", capture_output=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hci-windows-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home with spaces 設定"
        self.home.mkdir()
        self.root = self.home / "programs/herdr-codex-images"
        self.original = self.home / ".config/herdr-app"
        self.original.mkdir(parents=True)
        (self.original / "settings.json").write_text('{"zoom":1.25}')
        (self.original / "view.json").write_text('{"spaces":["existing-project"]}')
        self.project = self.home / "Documents/project/unfinished.txt"
        self.project.parent.mkdir(parents=True)
        self.project.write_text("unfinished project\n")
        self.profiles = [self.home / "Documents/WindowsPowerShell/profile.ps1", self.home / "Documents/PowerShell/profile.ps1"]
        for path in self.profiles:
            path.parent.mkdir(parents=True)
            path.write_bytes(b"# user settings\r\n$env:KEEP_ME='yes'\r\n")
        self.baseline = {p: p.read_bytes() for p in [self.project, *self.profiles, self.original / "settings.json", self.original / "view.json"]}

    def package(self, version="v0.1.0-test.1", unsafe=False):
        work = Path(self.temp.name) / version
        payload = work / "payload"
        payload.mkdir(parents=True)
        for name in ["herdr/herdr-app.exe", "codex/bin/codex.exe", "core/hc.exe", "core/herdr-core.exe", "codex/codex-path/rg.exe"]:
            target = payload / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.fixture, target)
        (payload / "tools").mkdir()
        for name in ["windows-common.ps1", "windows-manager.ps1"]:
            shutil.copy2(REPO / "tools" / name, payload / "tools" / name)
        shutil.copy2(self.shortcut,payload/'tools/windows-shortcut.dll')
        (payload / "VERSION").write_text(version + "\n")
        files = sorted(p for p in payload.rglob("*") if p.is_file())
        (payload / "FILES.sha256").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(payload).as_posix()}\n" for p in files))
        archive = work / f"herdr-codex-images-{version}-windows-x64.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            for file in payload.rglob("*"):
                if file.is_file():
                    output.write(file, "payload/" + file.relative_to(payload).as_posix())
            if unsafe:
                output.writestr("payload/../../must-not-extract", "unsafe")
        sums = work / "SHA256SUMS"
        sums.write_text(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
        return version, archive, sums

    def install(self, package, success=True, **overrides):
        version, archive, sums = package
        options = dict(Version=version, Archive=str(archive), Checksums=str(sums), InstallRoot=str(self.root),
                       CacheRoot=str(self.home / "cache"), SourceConfig=str(self.original),
                       ProfilePaths=[str(p) for p in self.profiles], ShortcutDirectory=str(self.home / "shortcuts"),
                       NoLaunch=True, NoShortcut=True)
        options.update(overrides)
        option_file = Path(self.temp.name) / "options.json"
        option_file.write_bytes(json.dumps(options, ensure_ascii=True).encode())
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = "$ErrorActionPreference='Stop'; try { $data=[IO.File]::ReadAllText(" + quote(option_file) + ")|ConvertFrom-Json; $options=@{}; foreach($p in $data.PSObject.Properties){$options[$p.Name]=$p.Value}; & " + quote(REPO / "install.ps1") + " @options } catch { [Console]::Error.WriteLine($_); exit 1 }"
        result = self.ps(command)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def manage(self, command, success=True):
        result = self.ps("& '" + str(self.root / "bootstrap.ps1").replace("'", "''") + "' '" + command + "'")
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def assert_originals(self, profiles=False):
        for path, data in self.baseline.items():
            if profiles or path not in self.profiles:
                self.assertEqual(path.read_bytes(),data,str(path))

    def test_install_preserves_original_settings_and_project(self):
        self.install(self.package())
        self.assert_originals()
        self.assertEqual((self.root / "app-home/view.json").read_bytes(),self.baseline[self.original / "view.json"])
        self.manage("doctor")

    def test_repeat_install_and_uninstall_keep_later_profile_edits(self):
        package = self.package()
        self.install(package)
        self.install(package)
        for path in self.profiles:
            self.assertEqual(path.read_text().count("# BEGIN herdr-codex-images-installer"),1)
            with path.open("ab") as output:
                output.write(b"# later user edit\r\n")
        self.manage("uninstall")
        for path in self.profiles:
            self.assertEqual(path.read_bytes(),self.baseline[path]+b"# later user edit\r\n")
        self.assertTrue((self.root / "app-home/view.json").exists())
        self.assertFalse((self.root / "install.json").exists())
        self.assert_originals()

    def test_update_and_rollback_preserve_separate_settings(self):
        self.install(self.package())
        (self.root / "app-home/settings.json").write_text('{"zoom":1.75}')
        self.install(self.package("v0.1.0-test.2"))
        self.assertEqual(json.loads((self.root / "install.json").read_text(encoding="utf-8"))["version"],"v0.1.0-test.2")
        self.manage("rollback")
        self.assertEqual(json.loads((self.root / "install.json").read_text(encoding="utf-8"))["version"],"v0.1.0-test.1")
        self.assertEqual((self.root / "app-home/settings.json").read_text(),'{"zoom":1.75}')
        self.manage("doctor")
        self.assert_originals()

    def test_corrupt_archive_never_activates(self):
        package = self.package()
        package[2].write_text("0"*64+"  "+package[1].name+"\n")
        self.install(package,success=False)
        self.assertFalse((self.root / "install.json").exists())
        self.assert_originals(profiles=True)

    def test_traversal_archive_is_rejected(self):
        self.install(self.package(unsafe=True),success=False)
        self.assertFalse((self.root / "must-not-extract").exists())
        self.assert_originals(profiles=True)

    def test_unmanaged_entry_is_preserved(self):
        self.root.mkdir(parents=True)
        (self.root / "bootstrap.ps1").write_text("unrelated user file")
        self.install(self.package(),success=False)
        self.assertEqual((self.root / "bootstrap.ps1").read_text(),"unrelated user file")
        self.assert_originals(profiles=True)

    def test_malformed_profile_is_unchanged(self):
        self.profiles[0].write_bytes(b"# BEGIN herdr-codex-images-installer\r\n# incomplete\r\n")
        self.baseline[self.profiles[0]] = self.profiles[0].read_bytes()
        self.install(self.package(),success=False)
        self.assertFalse((self.root / "install.json").exists())
        self.assert_originals(profiles=True)

    def test_profile_utf16_encoding_survives_install_and_uninstall(self):
        self.profiles[0].write_bytes("# 自訂設定\r\n$env:KEEP_ME='yes'\r\n".encode("utf-16"))
        self.baseline[self.profiles[0]] = self.profiles[0].read_bytes()
        self.install(self.package())
        self.manage("uninstall")
        self.assert_originals(profiles=True)

    def test_powershell7_profile_syntax_is_preserved_by_51_installer(self):
        self.profiles[1].write_bytes(b"# PowerShell 7 profile\r\n$value = $null ?? 'kept'\r\n")
        self.baseline[self.profiles[1]]=self.profiles[1].read_bytes()
        self.install(self.package())
        self.assertTrue(self.profiles[1].read_bytes().startswith(self.baseline[self.profiles[1]]))
        self.manage('uninstall')
        self.assert_originals(profiles=True)

    def test_tampered_runtime_is_not_reused(self):
        package=self.package()
        self.install(package)
        (self.root / "versions" / package[0] / "codex/bin/codex.exe").write_bytes(b"changed")
        self.manage("doctor",success=False)
        self.install(package,success=False)

    def test_only_herdr_shells_select_bundled_codex(self):
        self.install(self.package())
        profile = "'" + str(self.profiles[0]).replace("'", "''") + "'"
        result = self.ps("$ErrorActionPreference='Stop'; Remove-Item Env:HC_TERMINAL_ID -ErrorAction SilentlyContinue; $before=$env:Path; . " + profile + "; if($env:Path -ne $before){throw 'Normal shell PATH changed'}; $env:HC_TERMINAL_ID='test'; . " + profile + "; (Get-Command codex.exe).Source")
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(os.path.samefile(self.root / "versions/v0.1.0-test.1/codex/bin/codex.exe",result.stdout.strip()))

    def test_start_menu_entry_does_not_replace_original_shortcut(self):
        shortcuts=self.home/'shortcuts'
        shortcuts.mkdir()
        original=shortcuts/'Herdr.lnk'
        original.write_bytes(b'original shortcut')
        self.install(self.package(),NoShortcut=False)
        self.assertTrue((shortcuts/'Herdr Images.lnk').exists())
        self.manage('uninstall')
        self.assertFalse((shortcuts/'Herdr Images.lnk').exists())
        self.assertEqual(original.read_bytes(),b'original shortcut')

    def test_unmanaged_shortcut_is_not_overwritten(self):
        shortcuts=self.home/'shortcuts'
        shortcuts.mkdir()
        original=shortcuts/'Herdr Images.lnk'
        original.write_bytes(b'unrelated shortcut')
        self.install(self.package(),success=False,NoShortcut=False)
        self.assertEqual(original.read_bytes(),b'unrelated shortcut')
        self.assert_originals(profiles=True)

    def test_profile_write_failure_restores_already_written_profile(self):
        self.profiles[1].chmod(stat.S_IREAD)
        try:
            self.install(self.package(),success=False)
            self.assert_originals(profiles=True)
            self.assertFalse((self.root/'install.json').exists())
        finally:
            self.profiles[1].chmod(stat.S_IWRITE)

    def test_update_and_uninstall_keep_running_version_alive(self):
        package=self.package()
        self.install(package)
        executable=self.root/'versions'/package[0]/'herdr/herdr-app.exe'
        process=subprocess.Popen([str(executable),'--hold'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            self.assertIsNone(process.poll())
            self.install(self.package('v0.1.0-test.2'))
            self.assertIsNone(process.poll())
            self.manage('uninstall')
            self.assertIsNone(process.poll())
            self.assertTrue(executable.exists())
        finally:
            process.stdin.close()
            process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
