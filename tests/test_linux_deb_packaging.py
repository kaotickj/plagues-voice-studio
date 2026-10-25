"""Exercise real Debian metadata, ownership, symlinks and data boundaries."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_linux_deb', ROOT / 'scripts/package_linux_deb.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


@unittest.skipUnless(sys.platform == 'linux', 'Debian installer checks are Linux-only')
class DebianPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.app = self.root / 'App with spaces'
        self.app.mkdir()
        header = bytearray(64)
        header[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', header, 18, 62)
        executable = self.app / packager.EXECUTABLE
        executable.write_bytes(header)
        executable.chmod(0o755)
        import tomllib
        version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
        (self.app / 'BUILD-INFO.json').write_text(json.dumps({
            'version': version, 'libc': ['glibc', '2.39']}))

    def test_prerelease_ordering(self):
        for before, after in [('1.0.0a1', '1.0.0b1'), ('1.0.0b1', '1.0.0rc1'),
                              ('1.0.0rc1', '1.0.0rc2'), ('1.0.0rc2', '1.0.0'),
                              ('1.0.0', '1.0.1')]:
            with self.subTest(before=before):
                self.assertEqual(subprocess.run(['dpkg', '--compare-versions',
                    packager.debian_version(before), 'lt', packager.debian_version(after)]).returncode, 0)
        with self.assertRaises(ValueError):
            packager.debian_version('1.0.0\nDepends: bad')

    @unittest.skipUnless(shutil.which('dpkg-deb'), 'Debian packaging tools required')
    def test_real_deb_payload_and_control(self):
        (self.app / 'library-link').symlink_to(packager.EXECUTABLE)
        output = self.root / 'output'
        deb = packager.package(self.app, output)
        self.assertEqual(subprocess.check_output(['dpkg-deb', '-f', str(deb), 'Architecture'], text=True).strip(), 'amd64')
        control = subprocess.check_output(['dpkg-deb', '-f', str(deb)], text=True)
        self.assertIn('libc6 (>= 2.39)', control)
        self.assertIn('ffmpeg', control)
        self.assertEqual((output / 'SHA256SUMS.txt').read_text(),
                         f'{hashlib.sha256(deb.read_bytes()).hexdigest()}  {deb.name}\n')
        archive = self.root / 'payload.tar'
        with archive.open('wb') as stream:
            subprocess.run(['dpkg-deb', '--fsys-tarfile', str(deb)], stdout=stream, check=True)
        with tarfile.open(archive) as bundle:
            members = bundle.getmembers()
            self.assertTrue(all(m.uid == 0 and m.gid == 0 for m in members))
            names = {m.name.removeprefix('./') for m in members}
            self.assertTrue(all(n == '.' or n.startswith('usr') for n in names))
            base = str(packager.INSTALL_PATH)
            self.assertTrue(bundle.getmember('./' + base + '/library-link').issym())
            self.assertTrue(bundle.getmember('./usr/bin/plagues-voice-studio').mode & 0o111)
            self.assertIn('usr/share/applications/plagues-voice-studio.desktop', names)
            self.assertIn('usr/share/doc/plagues-voice-studio/LICENSES/GPL-3.0.txt', names)
        controls = self.root / 'controls'
        subprocess.run(['dpkg-deb', '-e', str(deb), str(controls)], check=True)
        self.assertEqual({p.name for p in controls.iterdir()}, {'control'})
        if shutil.which('desktop-file-validate'):
            desktop = self.root / 'studio.desktop'
            desktop.write_text(packager.DESKTOP)
            subprocess.run(['desktop-file-validate', str(desktop)], check=True)

    @unittest.skipUnless(shutil.which('dpkg-deb'), 'Debian packaging tools required')
    def test_build_glibc_controls_real_debian_dependency(self):
        provenance = self.app / 'BUILD-INFO.json'
        info = json.loads(provenance.read_text())
        for declared, minimum in [('2.39', '2.39'), ('2.41', '2.41'), ('2.28', '2.39')]:
            with self.subTest(declared=declared):
                info['libc'] = ['glibc', declared]
                provenance.write_text(json.dumps(info))
                deb = packager.package(self.app, self.root / ('glibc-' + declared))
                depends = subprocess.check_output(
                    ['dpkg-deb', '-f', str(deb), 'Depends'], text=True).strip()
                self.assertTrue(depends.startswith(f'libc6 (>= {minimum}), '), depends)

    def test_rejects_missing_malformed_or_non_glibc_build_metadata(self):
        provenance = self.app / 'BUILD-INFO.json'
        info = json.loads(provenance.read_text())
        for libc in (None, 'glibc 2.41', ['musl', '1.2.5'], ['glibc'],
                     ['glibc', 2.41], ['glibc', '2'], ['glibc', '2.41rc1'],
                     ['glibc', '2.41\nConflicts: important-package'],
                     ['glibc', '2.41), dangerous-package (>= 1']):
            with self.subTest(libc=libc):
                info['libc'] = libc
                provenance.write_text(json.dumps(info))
                output = self.root / 'malformed-output'
                with self.assertRaisesRegex(ValueError, 'glibc'):
                    packager.package(self.app, output)
                self.assertFalse(output.exists())

    def test_rejects_wrong_architecture_and_models(self):
        executable = self.app / packager.EXECUTABLE
        data = bytearray(executable.read_bytes())
        struct.pack_into('<H', data, 18, 183)  # AArch64 is not amd64.
        executable.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'amd64'):
            packager.validate_app(self.app)
        struct.pack_into('<H', data, 18, 62)
        executable.write_bytes(data)
        (self.app / 'accidental.onnx').write_bytes(b'weights')
        with self.assertRaisesRegex(ValueError, 'weights'):
            packager.validate_app(self.app)

    def test_rejects_external_symlinks_and_version_mismatch(self):
        link = self.app / 'outside-link'
        link.symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            packager.validate_app(self.app)
        link.unlink()
        (self.app / 'BUILD-INFO.json').write_text('{"version": "0.0.0"}')
        with self.assertRaisesRegex(ValueError, 'version'):
            packager.package(self.app, self.root / 'out')


if __name__ == '__main__':
    unittest.main()
