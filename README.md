# Plague's Voice Studio v0.3.0 RC1

**Created by Kaotick Jay.** Local AI voice production for narration, radio, character voices, and Bethesda game dialogue.

## Project roadmap and audio showcase

- [Future live website demo](ROADMAP.md): authenticated/rate-limited access to real speech generation is planned, not yet deployed.
- [Voice sample scripts and publication guidance](samples/README.md): three creator-supplied WAV examples have been prepared as MP3 previews for the Plagued Mods website package. Their original audio files are not yet in this application repository.

## Application Preview

![Plague's Voice Studio desktop interface showing the Help Center, voice production and Model Manager tabs](assets/product-screenshot.png)

**Speech-engine status:** **Chatterbox, Qwen3-TTS and IndexTTS 2.5 are supported.** The creator has confirmed real speech generation with all three on the Windows setup used for development. Qwen3-TTS Base 0.6B and IndexTTS 2.5 have produced working audio. This describes verified use on that machine; it does not guarantee compatibility with every GPU, every model size or future upstream release.

This is a **v0.3.0 release candidate**, separately installed from the v0.2.4 stable source. Do not overwrite or uninstall v0.2.4. The preserved stable archive has SHA-256 `23464fb7c541e000d03f2c47f14e18629fe70d97f1b9b4d4ebadf556776d5928`.

### What you can do

- Generate Chatterbox speech with Nano, Turbo, Original English, or Multilingual V3, including model-appropriate controls, narration markup, batch jobs, and WAV/MP3 output.
- Generate multilingual reference-voice speech with Qwen3-TTS Base models in a separate Python environment, with WAV output, diagnostic logs, cancellation, and reusable character profiles.
- Browse and audition existing recordings, preview/copy the exact saved input script (including vocal tags) from its same-name JSON sidecar, compare Qwen and IndexTTS when both are configured, and prepare Fallout 4 / Skyrim voice assets with user-supplied conversion tools.

**Memory note:** IndexTTS/Qwen3 and a local LLM writer can both demand substantial system RAM and paging capacity. On the creator's Windows machine, closing DJ Writer before rendering IndexTTS resolved an access-violation crash. Run heavy generators sequentially if resources are tight.


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

## Separate environments and data

| | Previous stable v0.2.4 | v0.3.0 multi-engine build |
|---|---|---|
| Executable | `PlaguesVoiceStudio024.exe` | `PlaguesVoiceStudio030Experimental.exe` |
| Data | `%LOCALAPPDATA%\PlaguesVoiceStudio-v021` | `%LOCALAPPDATA%\PlaguesVoiceStudio-v030-Experimental` |
| Settings | `KaotickJay/PlaguesVoiceStudio021` | `KaotickJay/PlaguesVoiceStudio030Experimental` |
| Windows installation | Stable app folder | `Plague's Voice Studio 0.3` (existing installation directory retained) |
| Voices | Writable stable v0.2.x | New imports writable; stable v0.2.x and v0.1.x read-only |
| Models | Chatterbox | Same Chatterbox core, optional Qwen/Index in separate Python processes |

Stable Bethesda project profiles are **not automatically imported**, preventing modifications to the stable data store. Recreate v0.3 mappings or manually back up/import compatible profiles only after verifying them.

## Building on Windows

A [Windows GitHub Actions build](https://github.com/kaotickj/plagues-voice-studio/actions/workflows/windows-build.yml) on `develop` packages the current code as a portable application and a **single-file Windows setup EXE**. The build bundles the selected Chatterbox model; Qwen3-TTS still uses a separately installed local Python runtime and is not bundled in the installer.

**Installer note:** The standalone setup EXE is approximately 3 GB. There are **no numbered disks or companion BIN files**. The GitHub workflow builds with Inno Setup 6.5.2 or newer, rejects any disk slices, and verifies that the installer can install on a fresh Windows runner before declaring the workflow successful. Download the `PlaguesVoiceStudio-develop-Windows-Standalone-Installer` artifact, extract the EXE from GitHub's ZIP, and run it normally.


Windows x64, Python 3.11, Git, internet for initial Chatterbox installation and model acquisition. Inno Setup 6 is optional.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 -Models turbo
```

The result is `dist\PlaguesVoiceStudio030Experimental\PlaguesVoiceStudio030Experimental.exe` after successful frozen metadata and GUI smoke tests. For bundling all **four Chatterbox models**, use `-FullOffline`; this does **not** install Qwen3-TTS or IndexTTS. If all models are already in the new source's `models\` directory, add `-SkipModels` to avoid downloading again.

To preview source UI with an already prepared `.venv-build` environment, run `PREVIEW_GUI.bat`. A source-code change does not update an existing EXE; rebuilding is required.

Qwen3-TTS and IndexTTS 2.5 use separately installed Python runtimes, following `OPTIONAL_ENGINES.md`. The application does not install their packages automatically. Use **Voice Engines → Test selected engine** before generating. This checks imports; actual synthesis requires installed model weights. Downloads may be large.

## Release-candidate validation

**Chatterbox script saving is implemented on the current source branch.** New Chatterbox WAV/MP3 renders should create a same-stem JSON with an exact original-script `text` field; Qwen3 and IndexTTS already save analogous metadata. In **Export Library**, selecting any recording with saved metadata previews the text and enables **Copy script**. A previously built Windows EXE is not updated automatically by a GitHub merge.

The RC Windows build first runs Chatterbox/JSON integration and Export Library regression tests, and then runs an expanded frozen-Windows GUI smoke test to verify JSON-to-Export-Library text preview and clipboard copying. A real Chatterbox render with a corresponding JSON sidecar is still required before final release. See **[Release candidate acceptance checklist](RELEASE_CANDIDATE_CHECKLIST.md)** for the specific pass criteria and steps.

## Testing status

The Python source and protocol have automated tests, and the creator has verified live Windows narration with Chatterbox, Qwen3-TTS and IndexTTS 2.5. This does **not** claim universal hardware support, Qwen3 1.7B validation, AMD GPU acceleration or Bethesda in-game compatibility. The Windows build runs a frozen Qt smoke test before packaging.

**Compatibility note:** Existing v0.3 executable filenames, settings identifiers and user-data folders still contain `Experimental` as a legacy technical identifier, **not** as a product status. Those paths have deliberately not been renamed, so existing voice references, installed engines, profiles and settings remain discoverable. The visible application and installer version is 0.3.0.

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

MIT applies to original project code subject to the included `LICENSE`. Chatterbox is by Resemble AI. PyQt6 and optional engines have their own licenses. In particular, IndexTTS 2.5 uses a **Bilibili Model Use License Agreement**. No optional engine weights, model code or vendor binaries are bundled. See `THIRD_PARTY_NOTICES.md` and upstream model cards before redistributing a bundle.
