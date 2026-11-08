#!/usr/bin/env python3
"""Opt-in real Linux export smoke test; requires user-supplied licensed tools.

Creates a NEW disposable Wine prefix and staging directories. Never uses a game
prefix or game installation output. Artifacts remain for inspection. This tests
file generation and audio integrity, not in-game animation quality.
"""
from pathlib import Path
import argparse
import array
import dataclasses
import hashlib
import importlib.util
import json
import math
import os
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wine', required=True, type=Path)
    parser.add_argument('--tools', required=True, type=Path, help='LipGenerator.exe, FonixData.cdf, xwmaencode.exe')
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--text-file', required=True, type=Path)
    parser.add_argument('--facefx', type=Path)
    parser.add_argument('--proton-default-dlls', action='store_true',
                        help='Copy six installed Proton default-prefix VKD3D DLLs into NEW test prefix only')
    parser.add_argument('--ffmpeg', default='/usr/bin/ffmpeg')
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix='pvs real linux export '))
    print('Validation artifacts:', root, flush=True)
    prefix = root / 'disposable wine prefix'
    env = dict(os.environ, WINEPREFIX=str(prefix), WINEDEBUG='-all')
    env.pop('LD_LIBRARY_PATH', None)
    if 'LD_LIBRARY_PATH_ORIG' in os.environ:
        env['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH_ORIG']
    report = {'python': platform.python_version(), 'platform': platform.platform(),
              'wine': str(args.wine), 'root': str(root), 'cases': []}
    def save():
        (root / 'validation.json').write_text(json.dumps(report, indent=2))
    def run(command, timeout=180):
        result = subprocess.run([str(x) for x in command], env=env, capture_output=True,
                                text=True, errors='replace', timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr[-3000:] or result.stdout[-3000:])
        return result
    report['wine_version'] = run([args.wine, '--version']).stdout.strip()
    boot = run([args.wine, 'wineboot.exe', '-u'])
    report['wineboot_diagnostics'] = boot.stderr[-3000:]
    assert (prefix / 'system.reg').is_file(), 'Wine initialization did not complete'
    if args.proton_default_dlls:
        vendor = args.wine.resolve().parent.parent / 'share/default_pfx/drive_c/windows'
        copied = []
        for arch in ('system32', 'syswow64'):
            for name in ('libvkd3d-1.dll', 'libvkd3d-shader-1.dll', 'libvkd3d-utils-1.dll'):
                source = vendor / arch / name
                destination = prefix / 'drive_c/windows' / arch / name
                if not source.is_file():
                    raise RuntimeError('Vendor default-prefix DLL missing: ' + str(source))
                if destination.exists():
                    raise RuntimeError('Refusing to replace existing test-prefix DLL: ' + str(destination))
                shutil.copy2(source, destination)
                copied.append({'source': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
        report['proton_default_prefix_dlls'] = copied
    save()
    source_module = Path(__file__).resolve().parents[1] / 'src/chatterbox_studio/bethesda_export.py'
    spec = importlib.util.spec_from_file_location('bethesda_linux_validation', source_module)
    backend = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = backend
    spec.loader.exec_module(backend)
    report['backend_sha256'] = hashlib.sha256(source_module.read_bytes()).hexdigest()
    staging, sidecars, scratch = [root / name for name in ('staging mod with spaces', 'source sidecars', 'scratch with spaces')]
    for path in (staging, sidecars, scratch):
        path.mkdir()
    tempfile.tempdir = str(scratch)
    setting = backend.BethesdaExportSettings(
        source_audio=str(args.source.resolve()), text=args.text_file.read_text(), game='fallout4',
        plugin_name='LinuxValidation.esp', voice_type='ValidationVoice', response_filename='official_000001_1',
        output_root=str(staging), facefx_path=str(args.tools / 'LipGenerator.exe'),
        fonix_path=str(args.tools / 'FonixData.cdf'), encoder_path=str(args.tools / 'xwmaencode.exe'),
        encoder_type='xwmaencode', ffmpeg_path=args.ffmpeg, destination_mode='mod_root',
        sidecar_root=str(sidecars), lip_backend='lipgenerator', tool_runner='wine',
        wine_path=str(args.wine), wine_prefix=str(prefix))
    reference = root / 'reference.wav'
    run([args.ffmpeg, '-v', 'error', '-nostdin', '-y', '-i', args.source,
         '-ac', '1', '-ar', '44100', '-c:a', 'pcm_s16le', reference])
    with wave.open(str(reference)) as wav:
        duration = wav.getnframes() / wav.getframerate()
    report['source_duration_seconds'] = duration
    def success(name, settings):
        started = time.time()
        assert not backend.expected_fuz_path(settings).exists()
        fuz = backend.export_dialogue(settings, report=lambda line: print(name, line, flush=True))
        version, lip, xwm = backend.read_fuz(fuz)
        stem = backend.response_stem(settings.response_filename)
        retained = sidecars / settings.plugin_name / settings.voice_type
        assert version == 1 and lip == (retained / (stem + '.lip')).read_bytes()
        assert xwm == (retained / (stem + '.xwm')).read_bytes()
        assert len(lip) >= 12 and fuz.stat().st_mtime >= started
        decoded = root / (name + ' decoded.wav')
        run([args.ffmpeg, '-v', 'error', '-nostdin', '-y', '-i', retained / (stem + '.xwm'),
             '-ac', '1', '-c:a', 'pcm_s16le', decoded])
        with wave.open(str(decoded)) as wav:
            seconds = wav.getnframes() / wav.getframerate()
            samples = array.array('h', wav.readframes(wav.getnframes()))
        if sys.byteorder != 'little':
            samples.byteswap()
        rms = math.sqrt(sum(x*x for x in samples) / len(samples))
        assert rms > 1 and abs(seconds - duration) < .25
        assert not list(scratch.iterdir()), 'Scratch directories leaked'
        item = {'name': name, 'passed': True, 'fuz_bytes': fuz.stat().st_size,
                'lip_bytes': len(lip), 'lip_header': list(struct.unpack('<III', lip[:12])),
                'xwm_bytes': len(xwm), 'roundtrip_equal': True, 'decoded_seconds': seconds,
                'decoded_rms_s16': rms, 'fresh_output': True, 'scratch_clean': True}
        report['cases'].append(item)
        save()
    success('official Fallout4', setting)
    if args.facefx:
        for game in ('fallout4', 'skyrim', 'skyrimse'):
            try:
                success('FaceFX ' + game, dataclasses.replace(setting, lip_backend='facefxwrapper',
                        facefx_path=str(args.facefx), game=game, response_filename='facefx_' + game + '_000001_1'))
            except backend.BethesdaExportError as exc:
                report['cases'].append({'name': 'FaceFX ' + game, 'passed': False, 'error': str(exc)})
                save()
                print('FaceFX failed:', exc, flush=True)
    # Real harmless local child processes simulate failure, not successful tools.
    sleeper = root / 'sleep tool.py'
    sleeper.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n')
    sleeper.chmod(0o700)
    fail_base = dataclasses.replace(setting, lip_backend='facefxwrapper', tool_runner='native',
                                    encoder_path='/bin/true', keep_intermediate=False)
    for name in ('missing output', 'timeout', 'cancel'):
        cfg = dataclasses.replace(fail_base, response_filename=name.replace(' ', '_'),
                                  facefx_path='/bin/true' if name == 'missing output' else str(sleeper),
                                  tool_timeout_seconds=1 if name == 'timeout' else 30)
        # Existing output must survive failed overwrite, and no partial remains.
        target = backend.expected_fuz_path(cfg)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'preserve existing voice')
        cfg = dataclasses.replace(cfg, overwrite_existing=True)
        start = time.monotonic()
        try:
            backend.export_dialogue(cfg, cancelled=lambda: name == 'cancel' and time.monotonic() - start > .4)
        except backend.BethesdaExportError as exc:
            expected = {'missing output': 'fresh LIP', 'timeout': 'timed out', 'cancel': 'cancelled'}[name]
            assert expected in str(exc), (name, str(exc))
            assert target.read_bytes() == b'preserve existing voice'
            assert not list(staging.rglob('*.pvs-partial')) and not list(staging.rglob('*.partial'))
            assert not list(scratch.iterdir())
            report['cases'].append({'name': name, 'passed': True, 'error': str(exc),
                                    'existing_output_preserved': True, 'scratch_clean': True,
                                    'seconds': round(time.monotonic() - start, 3)})
            save()
        else:
            raise AssertionError(name + ' unexpectedly succeeded')
    print(json.dumps(report, indent=2), flush=True)
    return 1 if any(not case['passed'] for case in report['cases']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
