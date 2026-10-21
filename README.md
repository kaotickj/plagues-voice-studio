# Plague's Voice Studio v1.0.0rc1

**Release candidate:** this is a prerelease for acceptance testing. See [RC notes](RELEASE_NOTES_1.0.0rc1.md) and [remaining release gates](RELEASE_READINESS.md).

Download the [Voice Studio RC installer or portable ZIP](https://github.com/kaotickj/plagues-voice-studio/releases/tag/v1.0.0rc1), with SHA-256 checksums.
The [separate DJ Writer 0.9.3 Vulkan update](https://github.com/kaotickj/plagues-voice-studio/releases/tag/dj-writer-v0.9.3) also provides installer and portable packages.

**Writer plugin:** source builds now include **Plugins → Promotional Writer** for
generic ad copy, promotions, announcements and custom writing. It uses a separate
local writing model and sends reviewed text to Narration Studio. The Goodneighbor
DJ standalone is not bundled. See [plugin setup and source testing](plugins/promotional-writer/README.md).

**Created by Kaotick Jay.** Local AI voice production for narration, radio, character voices, and Bethesda game dialogue.

## Project roadmap and audio showcase

- [Future live website demo](ROADMAP.md): authenticated/rate-limited access to real speech generation is planned, not yet deployed.
- [Voice sample scripts and publication guidance](samples/README.md): three creator-supplied WAV examples have been prepared as MP3 previews for the Plagued Mods website package. Their original audio files are not yet in this application repository.

## Application Preview

![Plague's Voice Studio desktop interface showing the Help Center, voice production and Model Manager tabs](assets/product-screenshot.png)

**Speech-engine status:** **Chatterbox, Qwen3-TTS and IndexTTS 2.5 are supported.** The creator has confirmed real speech generation with all three on the Windows setup used for development. Qwen3-TTS Base 0.6B and IndexTTS 2.5 have produced working audio. This describes verified use on that machine; it does not guarantee compatibility with every GPU, every model size or future upstream release.

**Kokoro preset speech:** Voice Engines also offers Michael, Fenrir, George,
Heart, Bella and Emma with speaking-speed controls and local ONNX inference.
Windows DirectML GPU acceleration is available for Radeon, Intel and NVIDIA;
CPU remains selectable. Auto prefers DirectML when its runtime is installed.
Kokoro cannot clone reference recordings; saved reference voices continue to use
Chatterbox, Qwen3 or IndexTTS. Run `scripts/setup_kokoro_windows.ps1` once; existing
shared weights are reused. Add `-DownloadModels` on a fresh machine to explicitly
download the checksum-verified model/voice pack. See [Kokoro setup](OPTIONAL_ENGINES.md#kokoro-preset-voices).

This **1.0.0rc1 candidate** upgrades the experimental 0.3 installation using its
existing installer identity and directory. It stores shared AI assets under
`%LOCALAPPDATA%\PlaguedAI` and preserves discovery of existing engine runtimes.
The separate v0.2.4 installation remains independent.

### What you can do

- Generate Chatterbox speech with Nano, Turbo, Original English, or Multilingual V3, including model-appropriate controls, narration markup, batch jobs, and WAV/MP3 output.
- Generate multilingual reference-voice speech with Qwen3-TTS Base models in a separate Python environment, with WAV output, diagnostic logs, cancellation, and reusable character profiles.
- Generate preset-voice speech with Kokoro, including US/UK pronunciation,
  speaking speed, character presets and WAV/script metadata.
- Browse and audition existing recordings, preview/copy the exact saved input script (including vocal tags) from its same-name JSON sidecar, compare Qwen and IndexTTS when both are configured, and prepare Fallout 4 / Skyrim voice assets with user-supplied conversion tools.

**Memory note:** IndexTTS/Qwen3 and a local LLM writer can both demand substantial system RAM and paging capacity. On the creator's Windows machine, closing DJ Writer before rendering IndexTTS resolved an access-violation crash. Run heavy generators sequentially if resources are tight.


## Checking for future updates

Voice Studio includes a **Check for updates** action in the top bar. It queries only the official [GitHub Releases](https://github.com/kaotickj/plagues-voice-studio/releases) API for newer stable releases. This check is manual by default; you can enable a single, non-blocking check on startup from the Updates dialog.

When a newer stable version is available, **View official release** opens the validated GitHub release page so you can review its notes and download the appropriate installer. The application does **not** download, execute, or replace software automatically; model runtimes, scripts, profiles, audio files, and installed voices remain unchanged. The update lookup sends no audio or script data. GitHub receives an ordinary request to its release metadata endpoint. Prereleases (including release candidates) are intentionally not promoted as stable updates.

Local RC installer upgrade, reinstall, repeated startup and data-preservation
checks pass. Fresh hosted Windows CI remains a publication gate; see
[release readiness](RELEASE_READINESS.md). Installers are currently unsigned.

## Live engine diagnostics and isolated runtimes

- No pop-up command prompt when launching optional Qwen / Index Python on Windows.
- On-screen engine stages, elapsed clock, persistent diagnostic logs, and Cancel.
- Logs saved under the existing v0.3 AppData folder in `engine_logs`.
- Model-download and CPU loading can still be slow. The new generation limit is 45 minutes.
- Existing engine environments and model weights are not changed.

**Rebuilding an existing v0.3 checkout:** Use the normal Windows build commands below, or the retained `REBUILD_ALPHA4_EXISTING.ps1` helper to reuse an already installed `.venv-build` without reinstalling packages or redownloading weights. Qwen3-TTS Base 0.6B and IndexTTS 2.5 have both generated working audio on the creator's Windows machine. GPU-specific acceleration and clean-machine packaging still need testing in each target environment.

## Alpha 3: External Python import-path isolation

**Fix for** `ImportError: Module use of python311.dll conflicts with this version of Python`.

Resetting the Windows DLL search path alone is insufficient because running
`<external-python> <bundled>/_internal/optional_engine_runner.py` prepends the
script directory to the external interpreter's `sys.path`. That directory
contains PyInstaller's Python 3.11 native extension modules. Alpha 3 adds
`-I` to the Python command for **both** engine probing and WAV generation;
this enables isolated mode and prevents automatic insertion of the script
directory while still allowing imports from the optional engine's venv.

First validate an installed Qwen3 runtime **outside** Voice Studio:

```powershell
$qwen = Join-Path $env:LOCALAPPDATA 'PlaguesVoiceStudio-v030-Experimental\engines\qwen3\Scripts\python.exe'
& $qwen -I .\optional_engine_runner.py --probe qwen3
```

Expected result is a final JSON object with `"ready": true`; warnings about
FlashAttention or SoX are separate issues. You must rebuild the EXE after
updating the launcher. This change does not reinstall models or dependencies.

## Alpha 2 Windows compatibility fix

Qwen3-TTS and IndexTTS run in external Python environments. Alpha 2 prevents the bundled Python 3.11 app from leaking its DLL search path into Python 3.12 optional-engine subprocesses. Rebuild the Windows EXE after updating the source. No optional-engine reinstall or model re-download is needed.

## Multi-engine features in v0.3.0

- **Qwen3-TTS** and **IndexTTS 2.5**, supported engines integrated through the **Voice Engines** tab. Qwen3 offers Base 0.6B/1.7B choices; IndexTTS supports configurable emotion and duration settings.
- Independent per-engine Python interpreters. Neither optional engine is installed or loaded by the Chatterbox host at startup.
- **Named character profiles** with per-engine model/language/device settings and shared reference voice. Saved to the independent v0.3 JSON storage.
- **A/B comparison**, rendering the same passage with both configured optional engines sequentially; measured rendering time, WAV outputs, playback and integration with the existing Bethesda exporter.
- **Separate app identity**, settings, installation, user data and export folder. Existing v0.2.x and v0.1.x voice references can be selected read-only.
- Process cancellation, JSON sidecar metadata and built-in configuration/probe validation.

**Scope:** Real Windows speech generation and WAV export have been reported working for Qwen3-TTS Base 0.6B and IndexTTS 2.5. Qwen3 1.7B and other acceleration configurations are not separately verified by this statement. Protocol unit tests still use a mock subprocess and do not replace clean-install/hardware testing. CPU synthesis can be slower than accelerated inference. External engine libraries and their weights are not redistributed.

Read **[OPTIONAL_ENGINES.md](OPTIONAL_ENGINES.md)** before setting up extra models. It includes the official upstream links, Windows installation scripts and license warnings.

## Existing features retained

- Chatterbox Nano, Turbo, Original English and Multilingual V3, unchanged Narration Studio generation pipeline.
- Source text import/export, markup (`[pause]`, `[rate]`, `[volume]`, `[emphasis]`) in Chatterbox narration, WAV/MP3, batch queue.
- Persistent saved voice references and an Export Library with playback of older recordings, script preview and Copy Script from matching JSON metadata.
- Bethesda project mappings, WAV/LIP/XWM/FUZ production, and optional direct game/mod installation using locally supplied conversion tools. Game plugin files are never edited.
- Dark-green branded PyQt6 GUI, searchable Help center, About/Credits/Diagnostics, and Windows frozen runtime & Qt smoke tests.

## Shared AI library and user data

The shared root is **`%LOCALAPPDATA%\PlaguedAI`** on Windows. Models, writing runtimes and voice references are shared across the tools, while Studio state lives in `apps/voice-studio` and DJ Writer state in `apps/dj-writer`. On Linux the root is `$XDG_DATA_HOME/PlaguedAI` (default `~/.local/share/PlaguedAI`). `PLAGUED_AI_HOME` overrides the shared root.

See [SHARED_AI_STORAGE.md](SHARED_AI_STORAGE.md) for the layout, explicit audit/migration scripts, hash-verified deduplication and compatibility links. The tools preserve voice IDs and existing model paths. Installed speech-engine Python environments stay at their original locations. Distinct speech and writing models remain separate; identical immutable files can share one physical copy.

Studio preserves its KaotickJay/PlaguesVoiceStudio settings identity and existing export locations. Legacy portable state can be copied on first launch, excluding heavy model/runtime directories. For a fully consolidated existing installation, close the tools and run the documented migration scripts before launching the updated builds.

## Separate environments and data

| | Previous stable v0.2.4 | v0.3.0 multi-engine build |
|---|---|---|
| Executable | `PlaguesVoiceStudio024.exe` | `PlaguesVoiceStudio030Experimental.exe` |
| Data | `%LOCALAPPDATA%\PlaguesVoiceStudio-v021` | `%LOCALAPPDATA%\PlaguedAI\apps\voice-studio` |
| Settings | `KaotickJay/PlaguesVoiceStudio021` | `KaotickJay/PlaguesVoiceStudio` (previous values preserved) |
| Windows installation | Stable app folder | `Plague's Voice Studio 0.3` (existing installation directory retained) |
| Voices | Writable stable v0.2.x | New imports writable; stable v0.2.x and v0.1.x read-only |
| Models | Chatterbox | Same Chatterbox core, optional Qwen/Index in separate Python processes |

Stable Bethesda project profiles are **not automatically imported**, preventing modifications to the stable data store. Recreate v0.3 mappings or manually back up/import compatible profiles only after verifying them.

## Distribution editions

**Standard Windows release: Slim/model-on-demand.** The automatic GitHub Actions build now uses `-Slim`. It packages the application and required Python libraries **without any Chatterbox model weight files**, even if the build checkout already contains `models/`. Install Voice Studio, open **Model Manager**, and download/validate the Chatterbox models you actually need. Qwen3 and IndexTTS require independently configured Python environments and their own models.

**Optional Full Offline edition:** `powershell -ExecutionPolicy Bypass -File .\\scripts\\build_windows.ps1 -FullOffline` still bundles every Chatterbox model. This may produce a multi-gigabyte installer beyond GitHub Releases' per-file asset limit; distribute it separately after size and license checks. It does not bundle Qwen3/IndexTTS.

**Build Slim locally:**

```powershell
powershell -ExecutionPolicy Bypass -File .\\scripts\\build_windows.ps1 -Slim
```

The slim build fails if accidentally bundled speech weight files are found in its output. No model weights are downloaded just to build the slim installer.

## Building on Windows

The [Windows build workflow](https://github.com/kaotickj/plagues-voice-studio/actions/workflows/windows-build.yml)
runs on application changes to `main`, `develop`, `release/**` and version tags.
The validated Windows CPU toolchain uses **Python 3.12** and the immutable
`requirements-release.txt` snapshot. The normal workflow builds a model-on-demand
portable ZIP and a single-file installer; it does not bundle speech/writer weights.

```powershell
./scripts/build_windows.ps1 -Slim
```

Git and internet are required for initial dependency installation. Inno Setup 6
is required for the installer; use `-SkipInstaller` for a portable-only build.
Use `-SkipDependencies` only with a matching, already prepared build environment.
Every release build checks dependency consistency, runs the complete regression
suite and exercises the actual frozen runtime and GUI/plugin menu before packaging.

The installed-application acceptance script uses a separate test-only AppId:

```powershell
./scripts/test_installer.ps1 -SourceDirectory 'dist/PlaguesVoiceStudio030Experimental'
```

It tests install, reinstall, repeated installed startup, uninstall and preservation
of seeded data/user-plugin files. Production Actions also install the real setup
on a fresh Windows runner and verify its runtime and GUI before publishing.

Tagged versions such as `v1.0.0rc1` can publish a **prerelease** only after the build
and installer jobs pass. Main-branch pushes create Actions artifacts, not a public
release. Published assets include the portable ZIP, setup EXE and SHA-256 manifest.
The size gate rejects files at or above 2 GiB and never splits the installer into
disks. Full-offline editions require separate size/license validation and hosting.

The legacy executable filename and default installation directory retain `030`
and `Experimental` for upgrade compatibility. The visible version is 1.0.0rc1;
AppData and QSettings identities remain permanent and unversioned. No engine
runtime or large model folder is moved. Actual new-candidate engine inference and
in-game Bethesda acceptance remain separate manual gates.

## Qwen3-TTS Base 1.7B cache verification

The creator has reported successful **1.7B cache checks**; actual candidate speech generation still needs validation. The official repository is several gigabytes, including a large weight file and a separate speech tokenizer. The Model Manager previously considered any Hugging Face cached *revision* sufficient evidence of model availability, even if needed files were absent. The improved check now opens the cached snapshot offline and verifies the main model and tokenizer files exist and are nonempty. The download task reports free disk space on the cache volume and confirms required files before recording success.

A failed 1.7B download still needs its diagnostic log reviewed; network interruptions, partial files, free disk space, Hugging Face cache/Xet behavior, and engine dependency compatibility may be involved. No cache or user model is deleted automatically. 0.6B stays supported.

## Model Manager: install models from the GUI

The **Model Manager** tab installs official Hugging Face model weights without requiring users to run model-download commands manually. Six model choices are available:

- Chatterbox Nano, Turbo, Original English and Multilingual V3.
- Qwen3-TTS Base 0.6B and 1.7B.

Choose a model, review its local status and select **Download selected model**. The operation runs in the background, shows log messages and supports Stop. Chatterbox transfers stop between individual files; Qwen transfers can terminate the isolated download subprocess. Partially downloaded files can generally be reused after restarting.

**Where files go:** Chatterbox weights are saved in the current user's application data under `models/<model-id>`, and Narration Studio automatically prefers validated downloaded weights to bundled files. Qwen weights go into the Hugging Face cache associated with the selected Qwen Python interpreter. **Check Qwen cache** detects a cached snapshot; only an actual generation confirms model inference. Existing Qwen caches are reused.

**Qwen runtime remains separate:** The Model Manager downloads model weights but does not install Python 3.12, `qwen-tts`, or a compatible PyTorch build. Configure the Qwen interpreter under **Voice Engines** first. IndexTTS 2.5 is supported through Voice Engines but remains outside the managed model list. No model is silently downloaded merely by opening Model Manager. Model downloads require network access and enough free disk space.

## Support Project Development

Plague's Voice Studio is independently developed by **Kaotick Jay**. If you would like to support maintenance, bug fixes, documentation, and continued development, contributions are voluntary:

- [GitHub Sponsors](https://github.com/sponsors/kaotickj)
- [Patreon](https://www.patreon.com/KaotickJay)
- [PayPal](https://paypal.me/kaotickj)

The links are also available under **Help → Support Project Development** in the application. The sponsor information is maintained in [`.github/FUNDING.yml`](.github/FUNDING.yml).

## Licensing

MIT applies to original project code subject to the included `LICENSE`. Windows GUI binaries include GPL PyQt6 and are distributed under GPL v3; see [BINARY_LICENSE.md](BINARY_LICENSE.md) for the full-license location and corresponding source directions. Chatterbox is by Resemble AI. Optional engines have their own terms; IndexTTS 2.5 uses a **Bilibili Model Use License Agreement**. Optional speech/writing engine weights and runtimes are not bundled in the standard slim package. See `THIRD_PARTY_NOTICES.md` and upstream model cards before redistributing model bundles.
