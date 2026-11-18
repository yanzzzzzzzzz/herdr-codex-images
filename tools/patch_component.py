#!/usr/bin/env python3
"""Validate and optionally apply one pinned native patch. Never deploy applications."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def load_manifest(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
    if manifest.get("schema") != 1 or not manifest.get("components"):
        raise ValueError("Unsupported or empty compatibility manifest")
    for name, entry in manifest["components"].items():
        if not re.fullmatch(r"[0-9a-f]{40}", entry["commit"]):
            raise ValueError(f"Invalid base commit for {name}")
        patch = (root / entry["patch"]).resolve()
        if not patch.is_relative_to(root) or not patch.is_file():
            raise ValueError(f"Patch must be a file inside the package: {name}")
        actual = hashlib.sha256(patch.read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ValueError(f"Patch SHA-256 mismatch: {name}")
    return manifest


def git(checkout, *args, check=True):
    result = subprocess.run(
        ["git", "-C", str(checkout), *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git exited {result.returncode}")
    return result


def patch_component(component, checkout, *, apply=False, root=ROOT):
    root = Path(root).resolve()
    manifest = load_manifest(root)
    if component not in manifest["components"]:
        raise ValueError(f"Unknown component: {component}")
    entry = manifest["components"][component]
    checkout = Path(checkout).resolve()
    top = Path(git(checkout, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if top != checkout:
        raise ValueError("Specify the upstream repository root, not a subdirectory")
    head = git(checkout, "rev-parse", "HEAD").stdout.strip()
    if head != entry["commit"]:
        raise ValueError(f"Wrong upstream commit: expected {entry['commit']}, found {head}")
    patch = root / entry["patch"]
    if git(checkout, "apply", "--reverse", "--check", str(patch), check=False).returncode == 0:
        return "Patch already applied; no files changed."
    if git(checkout, "status", "--porcelain").stdout.strip():
        raise ValueError("Checkout is not clean; use a dedicated upstream checkout")
    git(checkout, "apply", "--check", "--whitespace=error-all", str(patch))
    if apply:
        git(checkout, "apply", "--whitespace=error-all", str(patch))
        return "Patch applied. Build and deployment are separate steps."
    return "Patch is applicable. Re-run with --apply to change source files."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", nargs="?", choices=["herdr", "codex"])
    parser.add_argument("checkout", nargs="?", type=Path)
    parser.add_argument("--apply", action="store_true", help="apply to a clean pinned checkout")
    parser.add_argument("--validate", action="store_true", help="validate bundled patch hashes only")
    args = parser.parse_args()
    try:
        if args.validate:
            if args.component or args.checkout or args.apply:
                parser.error("--validate is used without a component, checkout, or --apply")
            manifest = load_manifest()
            print(f"Validated {len(manifest['components'])} patch hashes.")
        else:
            if not args.component or not args.checkout:
                parser.error("specify a component and upstream checkout, or use --validate")
            print(patch_component(args.component, args.checkout, apply=args.apply))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
