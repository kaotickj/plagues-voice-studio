"""Release regressions: real FFmpeg, structural xWMA, simulated Windows tools.

The simulated LIP/packet data cannot establish in-game FaceFX compatibility.
"""
from dataclasses import replace
from pathlib import Path
import struct
import subprocess
import wave

import pytest
from chatterbox_studio import bethesda_export as be


@pytest.mark.parametrize('form', [b'XWMA', b'WAVE'])
@pytest.mark.parametrize('codec', [0x0161, 0x0162])
def test_complete_wma_containers_accepted(xwma_bytes, form, codec):
    assert be.is_xwma(xwma_bytes(form=form, codec=codec, extra=[(b'JUNK', b'odd')]))


@pytest.mark.parametrize('kind', [
    'header_only', 'truncated', 'wrong_riff_size', 'trailing_bytes', 'pcm',
    'missing_fmt', 'missing_seek', 'missing_data', 'duplicate_data',
    'empty_data', 'empty_seek', 'misaligned_seek', 'backward_seek', 'short_fmt',
])
def test_corrupt_encoder_output_rejected(tmp_path, xwma_bytes, kind):
    audio = xwma_bytes()
    if kind == 'header_only':
        audio = b'RIFF' + struct.pack('<I', 16) + b'XWMAfmt broken'
    elif kind == 'truncated':
        audio = audio[:-1]
    elif kind == 'wrong_riff_size':
        audio = audio[:4] + struct.pack('<I', len(audio) + 100) + audio[8:]
    elif kind == 'trailing_bytes':
        audio += b'broken'
    elif kind == 'pcm':
        audio = xwma_bytes(codec=1)
    elif kind.startswith('missing_'):
        tag = {'fmt': b'fmt ', 'seek': b'dpds', 'data': b'data'}[kind[8:]]
        audio = xwma_bytes(omit=[tag])
    elif kind == 'duplicate_data':
        audio = xwma_bytes(extra=[(b'data', b'more')])
    else:
        tag, data = {
            'empty_data': (b'data', b''), 'empty_seek': (b'dpds', b''),
            'misaligned_seek': (b'dpds', b'123'),
            'backward_seek': (b'dpds', struct.pack('<II', 8192, 4096)),
            'short_fmt': (b'fmt ', b'\x61\x01'),
        }[kind]
        # Build a correctly sized RIFF around the malformed chunk payload.
        body = audio[8:]
        start = body.index(tag)
        old_size = struct.unpack_from('<I', body, start + 4)[0]
        body = (body[:start] + tag + struct.pack('<I', len(data)) + data + b'\0' * (len(data) % 2)
                + body[start + 8 + old_size + old_size % 2:])
        audio = b'RIFF' + struct.pack('<I', len(body)) + body
    assert not be.is_xwma(audio)
    target = tmp_path / 'keep.fuz'
    target.write_bytes(b'original')
    with pytest.raises(be.BethesdaExportError, match='RIFF/xWMA'):
        be.write_fuz(target, audio, b'LIP')
    assert target.read_bytes() == b'original'
    assert not list(tmp_path.glob('*.partial'))


@pytest.mark.parametrize('name', ['CON', 'nul.wav', 'Com1', 'LPT9.ext', 'COM¹',
                                 'CONOUT$', 'Voice.', ' Voice', 'Voice '])
def test_invalid_windows_names_rejected(name):
    with pytest.raises(be.BethesdaExportError):
        be.safe_segment(name, 'voice filename')


def test_incomplete_fuz_rejected(tmp_path, xwma_bytes):
    path = tmp_path / 'bad.fuz'
    for version, lip, audio in [(1, b'', xwma_bytes()), (2, b'LIP', xwma_bytes()),
                                (1, b'LIP', b'RIFFbroken')]:
        path.write_bytes(b'FUZE' + struct.pack('<II', version, len(lip)) + lip + audio)
        with pytest.raises(be.BethesdaExportError):
            be.read_fuz(path)


@pytest.fixture
def configured_export(tmp_path, monkeypatch, xwma_bytes):
    source = tmp_path / 'reference speech.wav'
    # Deliberately use stereo 24 kHz, unlike either required tool input format.
    with wave.open(str(source), 'wb') as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b'\0' * 24000 * 4)
    tools = tmp_path / 'Tools with spaces'
    tools.mkdir()
    facefx, encoder, fonix = [tools / name for name in ('FaceFXWrapper.exe', 'encoder.exe', 'FonixData.cdf')]
    for file in (facefx, encoder, fonix):
        file.write_bytes(b'test placeholder')
    data = tmp_path / 'Game with spaces' / 'Data'
    data.mkdir(parents=True)
    sidecars = tmp_path / 'project sources'
    sidecars.mkdir()
    settings = be.BethesdaExportSettings(
        source_audio=str(source), text='[chuckle] Hello "friend". [pause:1s]', game='fallout4',
        plugin_name='My Mod.esp', voice_type='MyVoice', response_filename='00000001_1.wav',
        output_root=str(data), facefx_path=str(facefx), encoder_path=str(encoder),
        fonix_path=str(fonix), sidecar_root=str(sidecars))
    state = {'audio': xwma_bytes(), 'lip': b'LIP fixture', 'game': 'Fallout4', 'fail': ''}
    calls = []
    real_call = be._call

    def call(args, action, **kwargs):
        calls.append(action)
        if action == state['fail']:
            raise be.BethesdaExportError('simulated converter failure')
        if action.endswith('audio preparation'):
            real_call(args, action, **kwargs)  # Actually exercise FFmpeg on this platform.
        elif action == 'FaceFX LIP generation':
            assert args[:4] == [str(facefx), state['game'], 'USEnglish', str(fonix)]
            assert len(args) == 7 and args[-1] == 'Hello "friend".'
            with wave.open(args[4], 'rb') as wav:
                assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) == (1, 2, 16000, 16000)
            if state['lip'] is not None:
                Path(args[5]).write_bytes(state['lip'])
        else:
            assert action in ('WMAEncodeRS encoding', 'Creation Kit xwmaencode encoding')
            source_wav = args[1] if action == 'WMAEncodeRS encoding' else args[3]
            with wave.open(source_wav, 'rb') as wav:
                assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) == (1, 2, 44100, 44100)
            if action == 'WMAEncodeRS encoding':
                assert args[3:] == ['--xwma', '-b', '48']
                target = args[2]
            else:
                assert args[1:3] == ['-b', '48000'] and len(args) == 5
                target = args[4]
            if state['audio'] is not None:
                Path(target).write_bytes(state['audio'])
    monkeypatch.setattr(be, '_call', call)
    return settings, state, calls


@pytest.mark.parametrize('game', ['fallout4', 'skyrim', 'skyrimse'])
@pytest.mark.parametrize('encoder', ['wmaencoders', 'xwmaencode'])
def test_complete_pipeline_all_games_and_encoders(configured_export, game, encoder):
    config, state, calls = configured_export
    state['game'] = 'Fallout4' if game == 'fallout4' else 'Skyrim'
    config = replace(config, game=game, encoder_type=encoder)
    path = be.export_dialogue(config)
    assert path == Path(config.output_root) / 'Sound' / 'Voice' / 'My Mod.esp' / 'MyVoice' / '00000001_1.fuz'
    assert be.read_fuz(path) == (1, state['lip'], state['audio'])
    assert {p.suffix for p in Path(config.output_root).rglob('*') if p.is_file()} == {'.fuz'}
    source_files = Path(config.sidecar_root) / 'My Mod.esp' / 'MyVoice'
    assert (source_files / '00000001_1.txt').read_text() == 'Hello "friend".'
    assert len(calls) == 4


def test_mo2_and_existing_file_backup(configured_export, tmp_path):
    config, state, calls = configured_export
    mod = tmp_path / 'MO2 mod'
    mod.mkdir()
    config = replace(config, output_root=str(mod), destination_mode='mod_root', keep_intermediate=False)
    target = be.expected_fuz_path(config)
    target.parent.mkdir(parents=True)
    target.write_bytes(b'original installed FUZ')
    with pytest.raises(be.BethesdaExportError, match='Output exists'):
        be.export_dialogue(config)
    assert not calls
    assert be.export_dialogue(replace(config, overwrite_existing=True)) == target
    backups = list(Path(config.sidecar_root).rglob('*.fuz.bak'))
    assert len(backups) == 1 and backups[0].read_bytes() == b'original installed FUZ'
    assert not list(mod.rglob('Data'))
    assert not list(Path(config.sidecar_root).rglob('*.wav'))


@pytest.mark.parametrize('kind', ['corrupt_audio', 'empty_audio', 'missing_audio', 'empty_lip', 'missing_lip', 'tool_failure'])
def test_failed_export_preserves_existing_assets(configured_export, kind):
    config, state, calls = configured_export
    config = replace(config, overwrite_existing=True)
    target = be.expected_fuz_path(config)
    target.parent.mkdir(parents=True)
    target.write_bytes(b'original installed FUZ')
    source = Path(config.sidecar_root) / 'My Mod.esp' / 'MyVoice' / '00000001_1.wav'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'original source WAV')
    if kind == 'corrupt_audio': state['audio'] = b'RIFF' + struct.pack('<I', 16) + b'XWMAfmt broken'
    elif kind == 'empty_audio': state['audio'] = b''
    elif kind == 'missing_audio': state['audio'] = None
    elif kind == 'empty_lip': state['lip'] = b''
    elif kind == 'missing_lip': state['lip'] = None
    else: state['fail'] = 'FaceFX LIP generation'
    with pytest.raises(be.BethesdaExportError):
        be.export_dialogue(config)
    assert target.read_bytes() == b'original installed FUZ'
    assert source.read_bytes() == b'original source WAV'
    assert not list(Path(config.output_root).rglob('*.pvs-partial'))
    assert not list(Path(config.sidecar_root).rglob('*.bak'))


def test_empty_prepared_audio_stops_before_facefx(configured_export, monkeypatch):
    config, state, calls = configured_export
    monkeypatch.setattr(be, '_call', lambda *_, **kw: None)
    with pytest.raises(be.BethesdaExportError, match='readable PCM WAV'):
        be.export_dialogue(config)
    assert not be.expected_fuz_path(config).exists()


def test_target_created_during_final_copy_is_not_overwritten(configured_export, monkeypatch):
    config, state, calls = configured_export
    target = be.expected_fuz_path(config)
    copy = be.shutil.copy2
    def competing_copy(source, destination, *args, **kwargs):
        result = copy(source, destination, *args, **kwargs)
        if str(destination).endswith('.pvs-partial'):
            target.write_bytes(b'created by another application')
        return result
    monkeypatch.setattr(be.shutil, 'copy2', competing_copy)
    with pytest.raises(be.BethesdaExportError, match='existing file was preserved'):
        be.export_dialogue(config)
    assert target.read_bytes() == b'created by another application'
    assert not list(target.parent.glob('*.pvs-partial'))


def test_tool_launch_failures_are_actionable(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError('cannot launch')
    monkeypatch.setattr(be.subprocess, 'Popen', fail)
    with pytest.raises(be.BethesdaExportError, match='FaceFX could not run'):
        be._call(['tool', 'text with spaces'], 'FaceFX')


def test_tool_nonzero_exit_is_not_success():
    import sys
    with pytest.raises(be.BethesdaExportError, match='exit 2.*encoder failed'):
        be._call([sys.executable, '-c', 'import sys; print("encoder failed", file=sys.stderr); sys.exit(2)'], 'XWM encoding')


def test_blank_destination_is_not_current_directory(configured_export):
    config, _, _ = configured_export
    with pytest.raises(be.BethesdaExportError, match='output directory'):
        be.expected_fuz_path(replace(config, output_root=''))
