#!/usr/bin/env python3
"""Make a Windows x64 runtime ZIP from explicit binaries, never user data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from check_codex_state import check_state_runtime

REPO = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(args, check=True, text=True, encoding="utf-8", errors="replace", capture_output=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("herdr-dir", "herdr-binary", "codex-dir", "codex-binary", "core-dir", "crt-dir", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--version", default="v0.1.0-preview.3")
    args = parser.parse_args()
    if os.name != "nt" or not re.fullmatch(r"v[0-9][A-Za-z0-9.-]*", args.version):
        parser.error("Requires a Windows builder and valid release tag")
    package_info = json.loads((args.codex_dir / "codex-package.json").read_text())
    if package_info.get("version") != "0.169.1" or package_info.get("target") != "x86_64-pc-windows-msvc":
        parser.error("Codex companions/resources must be the official Windows x64 0.169.1 bundle")
    args.output.mkdir(parents=True, exist_ok=True)
    asset = f"herdr-codex-images-{args.version}-windows-x64.zip"
    output = args.output / asset
    if output.exists():
        parser.error("Refusing to overwrite release asset")
    with tempfile.TemporaryDirectory(prefix="hci-windows-package-") as tmp:
        payload = Path(tmp) / "payload"
        (payload / "herdr").mkdir(parents=True)
        for name in ("herdr-app.svg", "LICENSE", "THIRD-PARTY-NOTICES"):
            shutil.copy2(args.herdr_dir / name, payload / "herdr" / name)
        shutil.copy2(args.herdr_binary, payload / "herdr/herdr-app.exe")
        shutil.copytree(args.codex_dir, payload / "codex")
        shutil.copy2(args.codex_binary, payload / "codex/bin/codex.exe")
        for name, source in (("LICENSE", "Codex-APACHE-2.0.txt"), ("NOTICE", "Codex-NOTICE.txt")):
            shutil.copy2(REPO / "licenses" / source, payload / "codex" / name)
        (payload / "core").mkdir()
        for name in ("hc.exe", "herdr-core.exe"):
            shutil.copy2(args.core_dir / name, payload / "core" / name)
        (payload / "core/conpty").mkdir()
        shutil.copy2(args.core_dir / "conpty/conpty.dll", payload / "core/conpty/conpty.dll")
        (payload / "core/conpty/x64").mkdir()
        shutil.copy2(args.core_dir / "conpty/x64/OpenConsole.exe", payload / "core/conpty/x64/OpenConsole.exe")
        shutil.copytree(args.core_dir / "THIRD-PARTY-NOTICES", payload / "core/THIRD-PARTY-NOTICES")
        crt_files = sorted(args.crt_dir.glob("*.dll"))
        assert {"vcruntime140.dll", "vcruntime140_1.dll"} <= {p.name.lower() for p in crt_files}
        for directory in (payload / "herdr", payload / "codex/bin", payload / "core"):
            for dll in crt_files:
                shutil.copy2(dll, directory / dll.name)
        (payload / "tools").mkdir()
        for name in ("windows-common.ps1", "windows-manager.ps1"):
            shutil.copy2(REPO / "tools" / name, payload / "tools" / name)
        shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        quote = lambda path: "'" + str(path).replace("'", "''") + "'"
        run(str(shell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
            "Add-Type -Path " + quote(REPO / "tools/windows-shortcut.cs") +
            " -OutputType Library -OutputAssembly " + quote(payload / "tools/windows-shortcut.dll"))
        for name in ("LICENSE", "NOTICE", "manifest.json"):
            shutil.copy2(REPO / name, payload / name)
        shutil.copytree(REPO / "licenses", payload / "licenses")
        (payload / "licenses/Microsoft-CRT-NOTICE.txt").write_text(
            "Microsoft Visual C++ Runtime\nCopyright Microsoft Corporation. All rights reserved.\n"
            "Unmodified application-local runtime DLLs are included.\n"
            "License: https://visualstudio.microsoft.com/license-terms/vs2026-ga-visualcpp-v14-redist-runtime/\n"
            "Distribution: https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution\n"
        )
        versions = {
            "herdr": run(str(payload / "herdr/herdr-app.exe"), "--version"),
            "codex": run(str(payload / "codex/bin/codex.exe"), "--version"),
            "core": run(str(payload / "core/hc.exe"), "--version"),
        }
        assert versions == {"herdr": "herdr-app 0.1.16", "codex": "codex-cli 0.169.1", "core": "hc 0.1.21"}, versions
        run(str(payload / "codex/bin/codex.exe"), "--help")
        run(str(payload / "codex/bin/codex.exe"), "resume", "--help")
        run(str(payload / "codex/codex-path/rg.exe"), "--version")
        state_compatibility = check_state_runtime(payload / "codex/bin/codex.exe")
        (payload / "VERSION").write_text(args.version + "\n")
        (payload / "build-info.json").write_text(json.dumps({
            "version": args.version, "platform": "windows-x64", "components": versions,
            "integration_commit": run("git", "-C", str(REPO), "rev-parse", "HEAD"),
            "codex_bundle": package_info,
            "state_compatibility": state_compatibility,
            "herdr_sha256": hashlib.sha256(args.herdr_binary.read_bytes()).hexdigest(),
            "codex_sha256": hashlib.sha256(args.codex_binary.read_bytes()).hexdigest(),
            "crt_files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in crt_files},
            "shortcut_source_sha256": hashlib.sha256((REPO / "tools/windows-shortcut.cs").read_bytes()).hexdigest(),
            "signing": "independent preview; patched executables are not Authenticode-signed",
        }, indent=2) + "\n")
        files = sorted(p for p in payload.rglob("*") if p.is_file())
        assert not any(p.is_symlink() for p in payload.rglob("*"))
        (payload / "FILES.sha256").write_text("".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(payload).as_posix()}\n" for p in files
        ))
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(p for p in payload.rglob("*") if p.is_file()):
                archive.write(path, "payload/" + path.relative_to(payload).as_posix())
    shutil.copy2(REPO / "install.ps1", args.output / "install.ps1")
    sha = hashlib.sha256(output.read_bytes()).hexdigest()
    script_sha = hashlib.sha256((args.output / "install.ps1").read_bytes()).hexdigest()
    (args.output / "SHA256SUMS").write_text(f"{sha}  {asset}\n{script_sha}  install.ps1\n")
    print(json.dumps({"archive": str(output), "bytes": output.stat().st_size, "sha256": sha}, indent=2))


if __name__ == "__main__":
    main()
