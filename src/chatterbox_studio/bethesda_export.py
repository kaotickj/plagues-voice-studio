"""Bethesda dialogue voice exports, independent of Chatterbox inference.

This module deliberately does NOT contain Creation Kit code, FonixData.cdf,
FaceFXWrapper, or a proprietary xWMA encoder. The user supplies their own
legally installed FaceFX-compatible tool and xWMA encoder. The FUZE container
writer is a clean Python implementation of the public container format.

Supported target game choices produce distinct LIP types; each must be checked
in-game by the user. Ordinary WAV/MP3 narration exports are unaffected.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Callable
import json
import os
import re
import shutil
import struct
import subprocess
import signal
import time
import wave


class BethesdaExportError(RuntimeError):
    """Actionable failure in export prerequisites or tool execution."""


class BethesdaExportCancelled(BethesdaExportError):
    """The user cancelled before publication; no partial FUZ is installed."""


def _check_cancelled(cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise BethesdaExportCancelled("Export cancelled")


GAMES = {"fallout4": "Fallout4", "skyrim": "Skyrim", "skyrimse": "Skyrim"}
ENCODERS = {"xwmaencode", "wmaencoders"}
FUZ_MAGIC = b"FUZE"
# Chatterbox marker tags are not dialogue words. Also remove PVS markup.
_TAG = re.compile(r"\[[^\[\]\r\n]*\]")
_SPACE = re.compile(r"\s+")
_BAD_SEGMENT = re.compile(r"[\\/\x00-\x1f<>:\"|?*]")
_RESERVED_SEGMENT = re.compile(r"^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)", re.I)


def clean_transcript(script: str) -> str:
    """Remove all bracketed synthesis directives from the dialogue transcript.

    The transcript must still be reviewed against the recorded audio, because
    a script's punctuation, pronunciation or spoken reactions may differ.
    """
    return _SPACE.sub(" ", _TAG.sub(" ", script)).strip()


def safe_segment(text: str, label: str) -> str:
    part = _BAD_SEGMENT.sub("_", text).strip(" .")
    if not part or part != text or _RESERVED_SEGMENT.match(part):
        raise BethesdaExportError(f"Enter a valid {label} without path separators or special characters")
    if len(part) > 120:
        raise BethesdaExportError(f"{label} is too long")
    return part


def is_xwma(data: bytes) -> bool:
    """Check RIFF bounds, WMA format, seek table and nonempty packet data.

    This validates the container, not the compressed audio's audible content.
    A RIFF/XWMA label alone does not establish that encoding succeeded.
    """
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] not in (b"XWMA", b"WAVE"):
        return False
    if struct.unpack_from("<I", data, 4)[0] + 8 != len(data):
        return False
    pos = 12
    chunks = {}
    while pos + 8 <= len(data):
        tag = data[pos:pos+4]
        size = struct.unpack_from("<I", data, pos+4)[0]
        start = pos + 8
        end = start + size
        pos = end + size % 2
        if pos > len(data):
            return False
        if tag in (b"fmt ", b"dpds", b"data"):
            if tag in chunks:
                return False
            chunks[tag] = data[start:end]
    if pos != len(data) or any(tag not in chunks for tag in (b"fmt ", b"dpds", b"data")):
        return False
    fmt, seek, packets = (chunks[tag] for tag in (b"fmt ", b"dpds", b"data"))
    if len(fmt) < 18 or not seek or len(seek) % 4 or not packets:
        return False
    codec, channels, rate, avg_bytes, block_align, bits, extra = struct.unpack_from("<HHIIHHH", fmt)
    # XAudio2 accepts WMA2 and WMA3. PCM (1) is never xWMA.
    if codec not in (0x0161, 0x0162) or not all((channels, rate, avg_bytes, block_align)):
        return False
    if len(fmt) < 18 + extra or bits != 16:
        return False
    previous = 0
    for (decoded_bytes,) in struct.iter_unpack("<I", seek):
        if decoded_bytes < previous or decoded_bytes % (channels * 2):
            return False
        previous = decoded_bytes
    return previous > 0


def write_fuz(path: Path, xwm: bytes, lip: bytes, *, version: int = 1) -> None:
    """Write a Bethesda FUZE container: header, LIP length/data, xWMA audio.

    This is packaging, not lip synthesis or xWMA encoding. Require plausible
    real xWMA and LIP data so a WAV mistakenly renamed XWM is rejected.
    """
    if not lip:
        raise BethesdaExportError("A non-empty LIP file is required for dialogue")
    if not is_xwma(xwm):
        raise BethesdaExportError("The encoder did not produce RIFF/xWMA audio")
    if version != 1 or len(lip) > 0xFFFFFFFF:
        raise BethesdaExportError("Invalid FUZ header values")
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(prefix=path.name + '.', suffix='.partial',
                            dir=path.parent, delete=False) as staged:
        partial = Path(staged.name)
    try:
        with partial.open("wb") as fh:
            fh.write(FUZ_MAGIC)
            fh.write(struct.pack("<II", version, len(lip)))
            fh.write(lip)
            fh.write(xwm)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def read_fuz(path: Path) -> tuple[int, bytes, bytes]:
    contents = path.read_bytes()
    if len(contents) < 12 or contents[:4] != FUZ_MAGIC:
        raise BethesdaExportError("Not a complete FUZE container")
    version, size = struct.unpack_from("<II", contents, 4)
    if size > len(contents) - 12:
        raise BethesdaExportError("LIP length exceeds FUZ file size")
    lip, xwm = contents[12:12+size], contents[12+size:]
    if version != 1 or not lip or not is_xwma(xwm):
        raise BethesdaExportError("FUZ must contain version 1, non-empty LIP and complete RIFF/xWMA audio")
    return version, lip, xwm


def audio_transcript(path: Path) -> str:
    """Read the output script, never the reference speaker's transcript.

    Older recordings may have no script metadata. Return empty text so the UI
    asks for the matching dialogue rather than retaining another line's script.
    """
    try:
        metadata = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        return ''
    text = metadata.get('text') if isinstance(metadata, dict) else None
    return clean_transcript(text) if isinstance(text, str) else ''


def _tool(path: str, label: str) -> str:
    path = path.strip().strip('"')
    if not path:
        raise BethesdaExportError(f"Select the {label} executable in the Bethesda Export tab")
    candidate = Path(path).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    found = shutil.which(path)
    if found:
        return found
    raise BethesdaExportError(f"Cannot find {label}: {path}")


def _stop_process(process: subprocess.Popen) -> None:
    """Stop only this invocation's process tree, never a shared wineserver."""
    if os.name == 'nt':
        if process.poll() is not None:
            return
        try:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, timeout=10,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
        return
    # A leader can exit on TERM while a child ignores it. Reap the leader, then
    # kill remaining members of its private session's group regardless of exit.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass


def _call(args: list[str], action: str, *, cwd: Path | None = None,
          env: dict[str, str] | None = None, timeout: int = 240,
          cancelled: Callable[[], bool] = lambda: False) -> str:
    """No shell, bounded diagnostics, cancellable tool process and timeout."""
    _check_cancelled(cancelled)
    process = None
    try:
        kwargs = ({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt'
                  else {'start_new_session': True})
        # File-backed capture avoids pipe deadlocks and unbounded RAM usage.
        with TemporaryDirectory(prefix='pvs_tool_log_') as logs:
            with (Path(logs) / 'out').open('w+b') as out, (Path(logs) / 'err').open('w+b') as err:
                process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=out,
                                           stderr=err, cwd=cwd, env=env, **kwargs)
                try:
                    deadline = time.monotonic() + timeout
                    while process.poll() is None:
                        _check_cancelled(cancelled)
                        if time.monotonic() >= deadline:
                            raise BethesdaExportError(f"{action} timed out after {timeout} seconds")
                        time.sleep(0.05)
                    _check_cancelled(cancelled)
                    def tail(file):
                        file.seek(0, os.SEEK_END)
                        file.seek(max(0, file.tell() - 8192))
                        return file.read().decode('utf-8', errors='replace').strip()
                    stdout, stderr = tail(out), tail(err)
                    if process.returncode:
                        details = '\n'.join(part for part in (stderr, stdout) if part) or 'No error text'
                        raise BethesdaExportError(f"{action} failed (exit {process.returncode}): {details[-1000:]}")
                    return stdout
                except BaseException:
                    _stop_process(process)
                    raise
                finally:
                    if process.poll() is None:
                        _stop_process(process)
    except OSError as exc:
        raise BethesdaExportError(f"{action} could not run: {exc}") from exc
    finally:
        if process is not None and process.poll() is None:
            _stop_process(process)


@dataclass(frozen=True)
class BethesdaExportSettings:
    source_audio: str
    text: str
    game: str
    plugin_name: str
    voice_type: str
    response_filename: str
    output_root: str
    facefx_path: str
    fonix_path: str
    encoder_path: str
    encoder_type: str = "wmaencoders"  # MIT Rust WMAEncodeRS, or CK xwmaencode
    bitrate_kbps: int = 48
    keep_intermediate: bool = True
    ffmpeg_path: str = ""
    destination_mode: str = "game_data"  # game_data or mod_root
    overwrite_existing: bool = False
    sidecar_root: str = ""  # separate project files from installed Game Data

    lip_backend: str = "facefxwrapper"  # or official FO4 LipGenerator
    tool_runner: str = "native"  # direct Windows tools, or Wine on Linux
    wine_path: str = ""
    wine_prefix: str = ""  # explicit, already initialized dedicated prefix
    tool_timeout_seconds: int = 240

    def validate(self) -> None:
        if self.game not in GAMES:
            raise BethesdaExportError("Choose Fallout 4, Skyrim, or Skyrim SE")
        if not Path(self.source_audio).is_file():
            raise BethesdaExportError("Select a WAV or MP3 file that already exists")
        if not clean_transcript(self.text):
            raise BethesdaExportError("Dialogue text is required for lip synchronization")
        for value, label in ((self.plugin_name, "plugin filename"), (self.voice_type, "voice type")):
            safe_segment(value, label)
        response_stem(self.response_filename)
        if Path(self.plugin_name).suffix.lower() not in {".esp", ".esm", ".esl"}:
            raise BethesdaExportError("Plugin filename must end in .esp, .esm, or .esl")
        if self.encoder_type not in ENCODERS:
            raise BethesdaExportError("Choose a supported encoder type")
        if self.bitrate_kbps not in (32, 48):
            raise BethesdaExportError("For 44.1 kHz mono speech, select 32 or 48 kbps")
        _validate_tools(self)
        if not self.output_root.strip():
            raise BethesdaExportError("Choose an output directory")
        if self.destination_mode not in ("game_data", "mod_root"):
            raise BethesdaExportError("Choose a supported installation target")
        if not Path(self.output_root).expanduser().is_dir():
            raise BethesdaExportError("Installation root must be an existing folder")
        if self.destination_mode == "game_data" and Path(self.output_root).name.casefold() != "data":
            raise BethesdaExportError("Game Data mode requires the actual game Data directory")
        if self.destination_mode == "mod_root" and Path(self.output_root).name.casefold() == "data":
            raise BethesdaExportError("MO2 mod mode requires the mod root, NOT a Data directory")
        if self.sidecar_root and not Path(self.sidecar_root).is_dir():
            raise BethesdaExportError("Source files directory must exist")


def _validate_tools(setting: BethesdaExportSettings) -> None:
    if setting.lip_backend not in ('facefxwrapper', 'lipgenerator'):
        raise BethesdaExportError("Choose FaceFXWrapper or official Fallout 4 LipGenerator")
    if setting.lip_backend == 'lipgenerator' and setting.game != 'fallout4':
        raise BethesdaExportError("Official LipGenerator is supported here for Fallout 4 only; choose FaceFXWrapper for Skyrim")
    if not Path(setting.fonix_path).expanduser().is_file():
        raise BethesdaExportError("Select FonixData.cdf from your locally installed Creation Kit")
    _tool(setting.facefx_path, 'LIP generator')
    _tool(setting.encoder_path, 'xWMA encoder')
    if setting.encoder_type not in ENCODERS:
        raise BethesdaExportError("Choose a supported encoder type")
    if setting.tool_runner not in ('native', 'wine'):
        raise BethesdaExportError("Choose native Windows tools or Wine")
    if not isinstance(setting.tool_timeout_seconds, int) or not 1 <= setting.tool_timeout_seconds <= 3600:
        raise BethesdaExportError("Tool timeout must be between 1 and 3600 seconds")
    if setting.tool_runner == 'wine':
        if os.name == 'nt':
            raise BethesdaExportError("Use native tools on Windows; Wine is for Linux")
        runner = Path(_tool(setting.wine_path, 'Wine executable (or Proton files/bin/wine)'))
        if not os.access(runner, os.X_OK):
            raise BethesdaExportError("The selected Wine executable is not executable")
        if runner.name.casefold() in ('proton', 'proton.exe'):
            raise BethesdaExportError("Select Proton's files/bin/wine executable, not the proton launcher")
        prefix = Path(setting.wine_prefix).expanduser()
        if not setting.wine_prefix or not prefix.is_absolute():
            raise BethesdaExportError("Select an absolute path to a dedicated, initialized Wine prefix")
        if not (prefix / 'system.reg').is_file() or not (prefix / 'dosdevices').is_dir():
            raise BethesdaExportError("Wine prefix is not initialized. Follow BETHESDA_LINUX.md: WINEPREFIX=... wineboot -u")
    elif os.name != 'nt':
        for path in (setting.facefx_path, setting.encoder_path):
            resolved = Path(_tool(path, 'Windows conversion tool'))
            with resolved.open('rb') as binary:
                windows_binary = binary.read(2) == b'MZ'
            if windows_binary:
                raise BethesdaExportError("Windows conversion tools need the Wine runner on Linux")
    if setting.ffmpeg_path:
        _tool(setting.ffmpeg_path, 'FFmpeg')


def diagnose_tools(setting: BethesdaExportSettings) -> list[str]:
    """Read-only setup checks. No prefix initialization, downloads or tool runs."""
    messages = []
    try:
        _validate_tools(setting)
        messages.append('Tool paths and runner configuration are valid.')
    except (BethesdaExportError, OSError) as exc:
        messages.append('Setup needed: ' + str(exc))
    try:
        messages.append('FFmpeg: ' + _ffmpeg_path(setting))
    except BethesdaExportError as exc:
        messages.append('Setup needed: ' + str(exc))
    if setting.tool_runner == 'wine':
        messages.append('Wine uses only the selected prefix. Use a dedicated export prefix, not a game prefix.')
    messages.append('Path checks do not prove runtime compatibility. Export a short recording into a staging mod folder, then test dialogue and lips in-game.')
    return messages


class _ToolRunner:
    def __init__(self, setting: BethesdaExportSettings, cancelled: Callable[[], bool]):
        self.setting = setting
        self.cancelled = cancelled
        self.env = None
        self.wine = None
        # Ckpid activates FaceFXWrapper's special CK IPC mode and ignores normal
        # CLI output paths. Never inherit it for this standalone export pipeline.
        if os.name != 'nt' or any(key.casefold() == 'ckpid' for key in os.environ):
            self.env = {key: value for key, value in os.environ.items() if key.casefold() != 'ckpid'}
        if os.name != 'nt':
            # Frozen Linux builds change search paths for bundled Qt/Python.
            # Those libraries must not leak into system Wine or native FFmpeg.
            self.env.pop('LD_LIBRARY_PATH', None)
            if 'LD_LIBRARY_PATH_ORIG' in os.environ:
                self.env['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH_ORIG']
        if setting.tool_runner == 'wine':
            self.wine = _tool(setting.wine_path, 'Wine')
            self.env.update(WINEPREFIX=str(Path(setting.wine_prefix).expanduser().resolve()), WINEDEBUG='-all')
            self.env.pop('WINEARCH', None)  # The initialized prefix defines its architecture.

    def call(self, args: list[str], action: str, *, cwd: Path | None = None, windows=False) -> str:
        if windows and self.wine:
            args = [self.wine, *args]
        return _call(args, action, cwd=cwd, env=self.env,
                     timeout=self.setting.tool_timeout_seconds, cancelled=self.cancelled)

    def path(self, path: Path | str) -> str:
        resolved = str(Path(path).expanduser().resolve())
        if not self.wine:
            return resolved
        value = self.call([self.wine, 'winepath.exe', '-w', resolved], 'Wine path conversion')
        if not re.match(r'^(?:[A-Za-z]:\\|\\\\)', value) or '\n' in value or '\r' in value:
            raise BethesdaExportError('Wine could not map a file path; check the selected prefix drive mappings')
        return value


def _ffmpeg_path(setting: BethesdaExportSettings) -> str:
    if setting.ffmpeg_path:
        return _tool(setting.ffmpeg_path, "FFmpeg")
    if os.name != 'nt':
        native = shutil.which('ffmpeg')
        if native:
            return native
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise BethesdaExportError("FFmpeg is required; install imageio-ffmpeg or choose its executable") from exc


def response_stem(filename: str) -> str:
    """Accept a CK basename (optionally with audio extension), never a path."""
    value = filename.strip()
    if not value or '/' in value or '\\' in value or value in ('.', '..'):
        raise BethesdaExportError('Supply the exact dialogue filename without any folder path')
    part = Path(value)
    if part.suffix and part.suffix.lower() not in ('.fuz', '.wav', '.lip', '.xwm'):
        raise BethesdaExportError('Response filename must have no extension or a voice-file extension')
    return safe_segment(part.stem if part.suffix else value, 'response filename')


def expected_fuz_path(setting: BethesdaExportSettings) -> Path:
    """Preview exact deploy path without invoking external tools.

    Root is either the game's existing Data/ folder or the root of a mod manager's
    mod folder. Both have Sound/Voice directly underneath, never Data/Data.
    """
    if not setting.output_root.strip():
        raise BethesdaExportError("Choose an output directory")
    root = Path(setting.output_root).expanduser().resolve()
    plugin = safe_segment(setting.plugin_name, "plugin filename")
    voice = safe_segment(setting.voice_type, "voice type")
    stem = response_stem(setting.response_filename)
    if not stem:
        raise BethesdaExportError("Enter an exact dialogue response filename")
    return root / "Sound" / "Voice" / plugin / voice / (stem + ".fuz")


def _check_prepared_wav(path: Path, rate: int) -> None:
    try:
        with wave.open(str(path), 'rb') as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, rate):
                raise BethesdaExportError(f"Audio preparation must produce {rate} Hz, 16-bit mono PCM")
            if audio.getnframes() == 0 or not audio.readframes(1):
                raise BethesdaExportError("Audio preparation produced an empty recording")
    except (OSError, EOFError, wave.Error) as exc:
        raise BethesdaExportError(f"Audio preparation did not produce a readable PCM WAV: {exc}") from exc


def export_dialogue(setting: BethesdaExportSettings, report: Callable[[str], None] = lambda _: None,
                    cancelled: Callable[[], bool] = lambda: False) -> Path:
    """Prepare dialogue using external tools, then deploy an atomic FUZ file.

    No ESP/ESM/ESL is parsed or modified. Caller supplies the precise expected
    response filename. Existing FUZ requires explicit overwrite permission and
    a separate backup; intermediates remain outside the game/mod folder.
    """
    _check_cancelled(cancelled)
    setting.validate()
    runner = _ToolRunner(setting, cancelled)
    fuz_path = expected_fuz_path(setting)
    root = Path(setting.output_root).expanduser().resolve()
    if not fuz_path.resolve().is_relative_to(root):
        raise BethesdaExportError('Destination contains a link outside the selected root')
    stem = fuz_path.stem
    plugin, voice = fuz_path.parent.parent.name, fuz_path.parent.name
    if fuz_path.exists() and not setting.overwrite_existing:
        raise BethesdaExportError(f"Output exists; approval required before replacing: {fuz_path}")
    # Deployable folders must contain only game assets, not debug source files.
    base = Path(setting.sidecar_root).expanduser().resolve() if setting.sidecar_root else Path(setting.source_audio).resolve().parent / 'PVS_Source_Files'
    sidecar_dir = base / plugin / voice
    ffmpeg = _ffmpeg_path(setting)
    facefx = _tool(setting.facefx_path, "FaceFXWrapper")
    encoder = _tool(setting.encoder_path, "xWMA encoder")

    with TemporaryDirectory(prefix="pvs_bethesda_") as tmp:
        scratch = Path(tmp)
        speech_wav = scratch / "lipsync_16khz.wav"
        encoding_wav = scratch / "encoding_44khz.wav"
        lip_file = scratch / (stem + ".lip")
        xwm_file = scratch / (stem + ".xwm")
        report("Resampling for lip sync (16 kHz, 16-bit mono)...")
        runner.call([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", setting.source_audio,
               "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(speech_wav)], "LIP audio preparation")
        _check_prepared_wav(speech_wav, 16000)
        report("Generating game-specific LIP animation...")
        if setting.lip_backend == 'lipgenerator':
            # Official FO4 LipGenerator reads FonixData.cdf and writes tmp16khz.wav
            # in its working directory. Never run it in the user's installation.
            local_tools = scratch / 'official_tools'
            local_tools.mkdir()
            local_exe = local_tools / 'LipGenerator.exe'
            shutil.copy2(facefx, local_exe)
            shutil.copy2(Path(setting.fonix_path).expanduser(), local_tools / 'FonixData.cdf')
            runner.call([runner.path(local_exe), runner.path(speech_wav), clean_transcript(setting.text),
                         '-OutputFileName:' + runner.path(lip_file)],
                        'Official Fallout 4 LIP generation', cwd=local_tools, windows=True)
        else:
            # Documented six-argument FaceFXWrapper form, with pre-resampled WAV.
            runner.call([runner.path(facefx), GAMES[setting.game], 'USEnglish',
                         runner.path(setting.fonix_path), runner.path(speech_wav),
                         runner.path(lip_file), clean_transcript(setting.text)],
                        'FaceFX LIP generation', cwd=scratch, windows=True)
        if not lip_file.is_file() or lip_file.stat().st_size == 0:
            raise BethesdaExportError("LIP generator returned success but did not produce a fresh LIP file")
        if setting.lip_backend == 'lipgenerator':
            data = lip_file.read_bytes()
            if len(data) < 12 or struct.unpack_from('<I', data)[0] != 1:
                raise BethesdaExportError('Official LipGenerator produced an invalid Fallout 4 LIP header')

        report("Resampling engine audio (44.1 kHz, 16-bit mono)...")
        runner.call([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", setting.source_audio,
               "-vn", "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(encoding_wav)], "XWM audio preparation")
        _check_prepared_wav(encoding_wav, 44100)
        report("Encoding xWMA audio...")
        if setting.encoder_type == "wmaencoders":
            runner.call([runner.path(encoder), runner.path(encoding_wav), runner.path(xwm_file), "--xwma",
                   "-b", str(setting.bitrate_kbps)], "WMAEncodeRS encoding", cwd=scratch, windows=True)
        else:
            runner.call([runner.path(encoder), "-b", str(setting.bitrate_kbps * 1000),
                   runner.path(encoding_wav), runner.path(xwm_file)], "Creation Kit xwmaencode encoding", cwd=scratch, windows=True)
        if not xwm_file.is_file() or xwm_file.stat().st_size < 12:
            raise BethesdaExportError("Encoder returned success but did not produce XWM audio")

        report("Packing Bethesda FUZ container...")
        lip_data, xwm_data = lip_file.read_bytes(), xwm_file.read_bytes()
        # Reject broken tool output before replacing any retained source files.
        candidate = scratch / 'candidate.fuz'
        write_fuz(candidate, xwm_data, lip_data)
        version, verified_lip, verified_xwm = read_fuz(candidate)
        if version != 1 or verified_lip != lip_data or verified_xwm != xwm_data:
            raise BethesdaExportError("FUZ round-trip validation failed")
        _check_cancelled(cancelled)
        if setting.keep_intermediate:
            sidecar_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(encoding_wav, sidecar_dir / (stem + ".wav"))
            shutil.copy2(lip_file, sidecar_dir / (stem + ".lip"))
            shutil.copy2(xwm_file, sidecar_dir / (stem + ".xwm"))
            (sidecar_dir / (stem + ".txt")).write_text(clean_transcript(setting.text), encoding="utf-8")
        _check_cancelled(cancelled)
        if not fuz_path.resolve().is_relative_to(root):
            raise BethesdaExportError('Destination contains a link outside the selected root')
        fuz_path.parent.mkdir(parents=True, exist_ok=True)
        if fuz_path.exists():
            if not setting.overwrite_existing:
                raise BethesdaExportError(f"Target exists: {fuz_path}")
            backup_root = sidecar_dir / 'backups'
            backup_root.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = backup_root / f'{stem}-{timestamp}.fuz.bak'
            shutil.copy2(fuz_path, backup)
            report(f"Backed up previous FUZ to: {backup}")
        # Separate application instances must not share the same partial file.
        with NamedTemporaryFile(prefix=fuz_path.name + '.', suffix='.pvs-partial',
                                dir=fuz_path.parent, delete=False) as staged:
            deploy_tmp = Path(staged.name)
        try:
            shutil.copy2(candidate, deploy_tmp)
            _check_cancelled(cancelled)
            if setting.overwrite_existing:
                os.replace(deploy_tmp, fuz_path)
            elif os.name == 'nt':
                # Windows rename refuses to replace an existing target, even
                # one created after the earlier existence check.
                os.rename(deploy_tmp, fuz_path)
            else:
                # POSIX rename replaces; link provides exclusive publication
                # of the already complete file on the same filesystem.
                os.link(deploy_tmp, fuz_path)
        except FileExistsError as exc:
            raise BethesdaExportError(f"Target appeared during export; existing file was preserved: {fuz_path}") from exc
        finally:
            deploy_tmp.unlink(missing_ok=True)
        if fuz_path.stat().st_size != candidate.stat().st_size:
            raise BethesdaExportError("Installed FUZ size mismatch")
        report(f"Voice package ready: {fuz_path}")
        return fuz_path
