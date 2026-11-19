"""Security checks for source-bound viewer manifests and installer hashes."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_viewer', REPO / 'tools/package_viewer.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class ViewerPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'source'
        for directory in ['viewer', 'tools']:
            (self.root / directory).mkdir(parents=True)
        for relative in ['viewer/Cargo.toml', 'viewer/Cargo.lock', 'tools/install-viewer.ps1.in']:
            shutil.copyfile(REPO / relative, self.root / relative)
        (self.root / '.gitignore').write_text('dist/\n')
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')
        self.binary = Path(self.temp.name) / 'binary-fixture'
        self.binary.write_bytes(b'never executed packaging fixture\n')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def invoke(self):
        args = ['package_viewer.py', '--tag', 'viewer-v0.2.0-preview.1', '--platform', 'windows-x64',
                '--binary', str(self.binary), '--output', str(self.root / 'dist')]
        with patch.object(package, 'ROOT', self.root), patch.object(sys, 'argv', args):
            package.main()

    def test_bootstrap_and_manifest_bind_exact_binary_and_clean_commit(self):
        self.invoke()
        manifest = json.loads((self.root / 'dist/viewer-manifest-windows-x64.json').read_text())
        expected = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        self.assertEqual(manifest['sha256'], expected)
        self.assertEqual(manifest['source_commit'], self.git('rev-parse', 'HEAD'))
        bootstrap = (self.root / 'dist/install-viewer.ps1').read_text()
        self.assertIn(expected, bootstrap)
        self.assertIn(manifest['source_commit'], bootstrap)
        self.assertNotIn('__BINARY_SHA256__', bootstrap)
        self.assertTrue((self.root / 'dist/viewer-sbom-windows-x64.cdx.json').is_file())

    def test_modified_source_cannot_claim_the_committed_build_identity(self):
        with (self.root / 'viewer/Cargo.toml').open('a') as file:
            file.write('\n# uncommitted source change\n')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.invoke()
        self.assertFalse((self.root / 'dist').exists())
