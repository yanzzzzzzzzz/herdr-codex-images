#!/usr/bin/env python3
"""Package only the standalone viewer built by the public source workflow."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--platform', choices=['windows-x64', 'macos-arm64', 'linux-x64'], required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    version = tomllib.loads((ROOT / 'viewer/Cargo.toml').read_text(encoding='utf-8'))['package']['version']
    if args.tag != 'viewer-v' + version or not re.fullmatch(r'viewer-v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?', args.tag):
        parser.error('Release tag must match the viewer crate version')
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=normal'], text=True)
    if dirty.strip():
        parser.error('A release must be packaged from a clean, committed source checkout')
    args.output.mkdir(parents=True, exist_ok=True)
    name = 'herdr-image-viewer-' + args.platform + ('.exe' if args.platform.startswith('windows') else '')
    output = args.output / name
    shutil.copyfile(args.binary, output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    if args.platform != 'linux-x64':
        suffix = 'ps1' if args.platform.startswith('windows') else 'sh'
        template = (ROOT / ('tools/install-viewer.' + suffix + '.in')).read_text(encoding='utf-8')
        text = template.replace('__TAG__', args.tag).replace('__COMMIT__', commit).replace('__BINARY_SHA256__', digest)
        (args.output / ('install-viewer.' + suffix)).write_bytes(text.encode('utf-8'))
    lock = tomllib.loads((ROOT / 'viewer/Cargo.lock').read_text(encoding='utf-8'))
    components = []
    for package in lock['package']:
        component = {'type': 'library', 'name': package['name'], 'version': package['version'],
                     'purl': f"pkg:cargo/{package['name']}@{package['version']}"}
        if 'checksum' in package:
            component['hashes'] = [{'alg': 'SHA-256', 'content': package['checksum']}]
        if 'source' in package:
            component['properties'] = [{'name': 'cargo:source', 'value': package['source']}]
        components.append(component)
    sbom = {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'version': 1, 'components': components}
    (args.output / f'viewer-sbom-{args.platform}.cdx.json').write_text(json.dumps(sbom, indent=2) + '\n', encoding='utf-8')
    manifest = {'schema': 1, 'tag': args.tag, 'platform': args.platform, 'source_commit': commit,
                'binary': name, 'sha256': digest, 'upstream_binaries_replaced': [],
                'signature': 'GitHub Actions provenance; no OS publisher signature'}
    (args.output / f'viewer-manifest-{args.platform}.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
