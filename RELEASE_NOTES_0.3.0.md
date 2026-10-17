# Plague's Voice Studio 0.3.0 RC1 — Multi-engine release candidate

**Current status (October 17, 2026):** Chatterbox, Qwen3-TTS and IndexTTS 2.5 are supported locally. The creator confirmed successful speech generation with all three on the Windows machine used for development. An IndexTTS crash encountered while DJ Writer was also running stopped recurring when DJ Writer was closed; this suggests resource contention on that machine, not a permanent IndexTTS incompatibility.

The full v0.3 application retains independently configured Python runtimes for Qwen3-TTS and IndexTTS. The independent v0.2.4 installation and data remain untouched. Engine weights, environment dependencies and licenses remain supplied/installed separately.

The Export Library can display and copy the exact script from a recording's matching JSON file when such metadata exists. The merged Chatterbox engine now writes a matching JSON containing the exact input script for each successful WAV/MP3 render. An installed EXE must be rebuilt to include that fix; older audio files without sidecars cannot be reconstructed automatically.

The release-candidate application version is **0.3.0rc1** and the installer label is **0.3.0-rc1**. Technical identifiers in executable names, paths, and Windows settings still include `Experimental` to preserve compatibility with existing installs and downloaded engine environments.

**RC acceptance:** The Windows GUI smoke test now exercises writing, previewing and copying script metadata without loading an AI model. A real newly built Chatterbox WAV/MP3 + JSON and Qwen3/IndexTTS regression check remain required before tagging a final release. See `RELEASE_CANDIDATE_CHECKLIST.md`.

**Test scope:** successful real generation is confirmed on the creator's Windows setup. That does not imply Qwen3 1.7B, every GPU configuration, or clean-machine installer testing. Historical alpha notes below record the development timeline rather than current engine support.

---

## Historical: 0.3.0-alpha4 development notes

Base: exact v0.2.4 stable source. Stable source frozen separately.

- Added pure JSON/subprocess optional backend protocol, avoiding any Qwen or Index dependencies in the core application process.
- Added Qwen3-TTS Base voice-clone and IndexTTS 2.5 inference runner stubs with real upstream Python API entrypoints; these require separate installs and target-hardware tests.
- Added Optional Engine Lab GUI: engine selection, install/runtime locations, import probe, voice-reference selection, character profiles with per-engine settings, same-script two-engine comparison, WAV listening and Bethesda handoff.
- Separate settings, data, voice imports, exports and Inno Setup identity. v0.2.x and v0.1.x saved voices remain read-only, and stable code/data are not overwritten.
- Added a first-use Qwen environment script and license-gated IndexTTS environment script. Neither optional engine is included in the core build.
- Added unit tests for JSON IPC, saved profiles, validation, cancellation-before-start, output provenance and optional runner bundling. The Windows GUI smoke test checks the new Lab tab without importing optional model code.

**Known limitations:** No successful real Qwen or Index inference validated in this environment. CPU performance and AMD acceleration unverified. Optional-engine script markup, speech chunking/MP3, multi-speaker scene composition and full project queue integration are planned later. Comparison is sequential, not simultaneous.

## Alpha 2: Windows optional-interpreter DLL isolation

- Fixed an error seen when the frozen Python 3.11 app launches optional Python 3.12 engines: `ImportError: Module use of python311.dll conflicts with this version of Python`.
- Reset PyInstaller's Windows DLL search directory only during optional child creation, then restore the original bundle directory in a `finally` block. Serialized child launches to limit process-wide DLL-directory exposure.
- Sanitize child Python environment (`PYTHONPATH`, `PYTHONHOME`, PyInstaller runtime markers and bundled PATH entries).
- Fixed both engine import probes and generation subprocesses, not just Qwen.
- Added regression coverage for clean child environment, probe, generation and restoration on launch failures.
- Neither Chatterbox generation nor the v0.2.4 stable release is changed. Requires rebuilding the frozen Windows executable.

## Alpha 3 correction (2026-10-16)

- Fixed Python 3.12 optional-engine subprocess import contamination from the
  frozen application's Python 3.11 `_internal` script directory.
- Qwen3 / IndexTTS probe and generation now run with `python -I`.
- Added regression tests for a hostile/bundled runner directory and both routes.
- The existing DLL search path reset, PATH sanitization and stable Chatterbox
  environment separation are retained.
- Not tested against a live Qwen model on Windows; verify in Optional Engine Lab.

## Alpha 4: visible engine diagnostics (2026-10-16)

- Optional Python launched with `-I -u` for isolation and real-time flushed logs.
- On Windows, suppress stray Python console windows via CREATE_NO_WINDOW.
- Visible GUI runtime status and elapsed clock; live scrollable stage/diagnostics output.
- Persist probe and generation logs under experimental user data, with Open diagnostic logs button.
- Stage messages distinguish imports, CPU/model loading, download, synthesis and WAV writing.
- Alert when no log output arrives for two minutes; use Cancel rather than guessing.
- Reduced generation limit from two hours to 45 minutes (including first-time downloads).
- Added cancellation to import probe and guarded cancellation/timeouts with process cleanup.
- Explicit low-disk warning during first model load.
- No model weights, voice recordings, or Qwen environment changes.

**Validation limitation:** Static and mocked-process tests only in Linux; real Windows
PyInstaller behavior, Qwen CPU timing, progress output and synthesis require
on-machine verification.
