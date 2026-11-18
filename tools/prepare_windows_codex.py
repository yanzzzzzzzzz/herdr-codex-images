#!/usr/bin/env python3
"""Prepare migration source bytes compatible with official Windows Codex databases."""
import argparse
import os
from pathlib import Path
import subprocess

from patch_component import git, load_manifest


def prepare_migrations(checkout, *, apply=False):
    checkout = Path(checkout).resolve()
    paths = git(checkout, "ls-files", "-z", "--", "codex-rs/state").stdout.split("\0")
    if not any(path.endswith(".sql") for path in paths):
        raise ValueError("No tracked Codex migration sources found")
    changes = []
    for relative in paths:
        if not relative.endswith(".sql"):
            continue
        path = checkout / relative
        if path.is_symlink() or not path.resolve().is_relative_to(checkout):
            raise ValueError("Migration source must remain inside the checkout")
        canonical = subprocess.check_output(["git", "-C", str(checkout), "show", "HEAD:" + relative])
        canonical = canonical.replace(b"\r\n", b"\n")
        current = path.read_bytes()
        if current.replace(b"\r\n", b"\n") != canonical:
            raise ValueError("Migration has semantic changes; unchanged: " + relative)
        target = canonical.replace(b"\n", b"\r\n")
        if current != target:
            changes.append((path, target))
    if apply:
        for path, target in changes:
            path.write_bytes(target)
    return len(changes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    if Path(git(checkout, "rev-parse", "--show-toplevel").stdout.strip()).resolve() != checkout:
        parser.error("Specify the upstream repository root")
    expected = load_manifest()["components"]["codex"]["commit"]
    if git(checkout, "rev-parse", "HEAD").stdout.strip() != expected:
        parser.error("Use the pinned Codex checkout")
    if args.apply and os.name != "nt":
        parser.error("CRLF preparation is for Windows builds only")
    count = prepare_migrations(checkout, apply=args.apply)
    print(f"{'Prepared' if args.apply else 'Would prepare'} {count} migration sources as CRLF; no databases are read or modified.")


if __name__ == "__main__":
    main()
