#!/usr/bin/env python3
"""Package explicitly supplied, validated binaries; never collect user config."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tarfile
import tempfile

REPO = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("app", "codex", "core", "output", "core-license"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if os.uname().sysname != "Darwin" or os.uname().machine != "arm64":
        parser.error("Packaging requires a macOS arm64 builder.")
    if not re.fullmatch(r"v[0-9][A-Za-z0-9.-]*", args.version):
        parser.error("Invalid release tag")
    args.output.mkdir(parents=True, exist_ok=True)
    asset = f"herdr-codex-images-{args.version}-macos-arm64.tar.gz"
    output = args.output / asset
    if output.exists():
        parser.error(f"Refusing to overwrite {output}")
    with tempfile.TemporaryDirectory(prefix="hci-package-") as tmp:
        payload = Path(tmp) / "payload"
        payload.mkdir()
        app = payload / "Herdr Images.app"
        shutil.copytree(args.app, app)
        plist = app / "Contents/Info.plist"
        info = plistlib.loads(plist.read_bytes())
        info.update(CFBundleIdentifier="io.github.yanzzzzzzzzz.herdr-codex-images",
                    CFBundleName="Herdr Images", CFBundleDisplayName="Herdr Images")
        info.pop("LSEnvironment", None)
        plist.write_bytes(plistlib.dumps(info))
        shutil.copytree(args.codex, payload / "codex")
        codex = payload / "codex/bin/codex"
        before = codex.stat().st_size
        # Remove symbol/debug metadata on the release copy, not the user's binary.
        run("xcrun", "strip", "-S", "-x", str(codex))
        run("codesign", "--force", "--sign", "-", str(codex))
        after = codex.stat().st_size
        core = payload / "core/Herdr Core.app"
        shutil.copytree(args.core, core)
        core_bin = payload / "core/bin"
        core_bin.mkdir()
        (core_bin / "hc").write_text('#!/bin/sh\nset -eu\nroot=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)\nexec "$root/Herdr Core.app/Contents/MacOS/herdr-core" "$@"\n')
        (core_bin / "hc").chmod(0o755)
        (payload / "bin").mkdir()
        shutil.copy2(REPO / "tools/herdr-images.sh", payload / "bin/herdr-images")
        (payload / "bin/herdr-images").chmod(0o755)
        shutil.copy2(REPO / "install.sh", args.output / "install.sh")
        for name in ("LICENSE", "NOTICE", "manifest.json"):
            shutil.copy2(REPO / name, payload / name)
        shutil.copytree(REPO / "licenses", payload / "licenses")
        shutil.copy2(args.core_license, payload / "licenses/herdr-core-LICENSE")
        entitlement = payload / "macos-entitlements.plist"
        entitlement.write_bytes(plistlib.dumps({
            "com.apple.security.cs.allow-jit": True,
            "com.apple.security.device.audio-input": True,
            "com.apple.security.device.camera": True,
            "com.apple.security.automation.apple-events": True,
        }))
        run("codesign", "--force", "--sign", "-", "--entitlements", str(entitlement), str(app))
        run("codesign", "--verify", "--deep", "--strict", str(app))
        run("codesign", "--verify", "--deep", "--strict", str(core))
        versions = {
            "herdr": run(str(app / "Contents/MacOS/Herdr"), "--version"),
            "codex": run(str(codex), "--version"),
            "core": run(str(core_bin / "hc"), "--version"),
        }
        assert versions == {"herdr": "herdr-app 0.1.16", "codex": "codex-cli 0.169.1", "core": "hc 0.1.21"}, versions
        run(str(codex), "--help")
        run(str(codex), "resume", "--help")
        run(str(payload / "codex/codex-path/rg"), "--version")
        (payload / "VERSION").write_text(args.version + "\n")
        (payload / "build-info.json").write_text(json.dumps({
            "version": args.version, "platform": "macos-arm64", "components": versions,
            "integration_commit": run("git", "-C", str(REPO), "rev-parse", "HEAD"),
            "codex_unstripped_bytes": before, "codex_stripped_bytes": codex.stat().st_size,
            "signing": "Herdr Images and Codex are locally ad-hoc signed, not notarized releases",
        }, indent=2) + "\n")
        entries = sorted(p for p in payload.rglob("*") if p.is_file())
        assert not any(p.is_symlink() for p in payload.rglob("*"))
        checksums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(payload)}\n" for p in entries)
        (payload / "FILES.sha256").write_text(checksums)
        with tarfile.open(output, "w:gz", compresslevel=6) as archive:
            archive.add(payload, arcname="payload", recursive=True)
    sha = hashlib.sha256(output.read_bytes()).hexdigest()
    installer_sha = hashlib.sha256((args.output / "install.sh").read_bytes()).hexdigest()
    (args.output / "SHA256SUMS").write_text(f"{sha}  {asset}\n{installer_sha}  install.sh\n")
    print(json.dumps({"archive": str(output), "bytes": output.stat().st_size, "sha256": sha,
                      "codex_before_bytes": before, "codex_after_bytes": after}, indent=2))


if __name__ == "__main__":
    main()
