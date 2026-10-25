# Speech engines: Qwen3-TTS, IndexTTS 2.5 and Kokoro

**Baseline:** Plague's Voice Studio v0.2.4 remains unchanged. The separate v0.3.0 build retains the four Chatterbox models in **Narration Studio** and supports both Qwen3-TTS and IndexTTS 2.5 through **Voice Engines**. Real speech generation with both has been confirmed on the creator's Windows machine. Keep independent engine runtimes out of `.venv-build` and the PyInstaller distribution folder.

## Engine status and requirements

| Adapter | Functional interface | Requirements | Verified here |
| --- | --- | --- | --- |
| Qwen3-TTS | 0.6B Base and 1.7B Base choices, reference-voice cloning, English and 9 other languages, WAV | Separate Python 3.12, `qwen-tts`, model weights (download on first use) | Windows CPU speech generation confirmed with 0.6B Base; 1.7B not separately confirmed |
| IndexTTS 2.5 | Reference-voice cloning, five languages, optional emotion vector, duration factor, WAV | Separate `uv` environment, official `index-tts` checkout and `checkpoints/` weights | Successful Windows speech generation confirmed by the creator |
| Kokoro | Six preset English voices, automatic US/UK accent, speaking speed, WAV | Separate Python 3.12, kokoro-onnx 0.6.1, ONNX DirectML/CPU runtime, shared INT8 model and voice pack | All six voices rendered on CPU and Radeon DirectML; see KOKORO_VALIDATION.md |

## Kokoro preset voices

Kokoro uses prepared voice embeddings; it cannot clone a speaker from WAV/MP3
reference audio. Your saved reference voices remain available in Chatterbox,
Qwen3 and IndexTTS. The six exposed presets are Michael, Fenrir, George, Heart,
Bella and Emma. Pronunciation follows the preset's US/UK accent.

1. Install Python 3.12 and run `scripts/setup_kokoro_windows.ps1`. This creates
   `%LOCALAPPDATA%\PlaguedAI\runtimes\python\kokoro-directml`, with no changes to
   Chatterbox/Qwen/Index packages. Existing models are reused from
   `%LOCALAPPDATA%\PlaguedAI\models\speech\kokoro`.
   Use `-Backend CPU` for a separate CPU-only runtime under `runtimes/python/kokoro-onnx`.
2. On a fresh machine add `-DownloadModels` to explicitly download
   `kokoro-v1.0.int8.onnx` and `voices-v1.0.bin` from the pinned upstream
   model-files-v1.1 release, with SHA-256 verification. Existing differing files
   are never overwritten. Custom `-EnvironmentDir` and `-ModelDirectory` are
   supported, as is the shared `PLAGUED_AI_HOME` override.
3. Restart Studio, open **Voice Engines**, and choose **Kokoro**. Default paths
   are detected automatically; custom runtime/model paths can be saved there.
   **Test selected engine** checks imports, files and voice-pack entries; it
   does not claim successful inference.
4. Select a voice, enter plain spoken text, and **Generate with selected engine**.
   Speaking speed 1.0 is normal; higher is faster. Save a character profile to
   retain the preset and speed. No reference recording or transcript is used.
5. Preview the WAV, find its script/voice metadata in Export Library, or send it
   to Bethesda Export. Cancel terminates the owned engine process. The cloning
   comparison remains limited to Qwen/Index because Kokoro cannot reproduce
   their reference voice.

**Auto** prefers DirectML GPU when available; **DirectML GPU** explicitly requires
it, while **CPU** remains selectable in either runtime. DirectML uses DirectX 12
on Windows, independently of the writers' Vulkan backend. The GPU runtime includes
ONNX tools to create one cached padding-compatible graph under the shared model
folder's `directml/` directory. Original model bytes and learned tensors remain
unchanged. Unsupported operations still execute on CPU. Backend/providers and the
actual graph path are recorded in the WAV sidecar. See [validation](KOKORO_VALIDATION.md).

The setup helper keeps CPU and DirectML distributions in separate environments.
For DirectML it explicitly installs kokoro-onnx without its upstream CPU-runtime
dependency, because both ONNX distributions provide the same Python module and
must not overwrite each other. All required dependencies are pinned in the helper.

Kokoro does not process
Chatterbox narration markup. Packages and weights are separate from the slim
app; the setup helper is included under `_internal/scripts` in portable builds.
Use `python scripts/validate_kokoro.py` to render real samples through Studio's
protocol. Add `--device directml --profile` to verify actual GPU operation events.
Model and runtime credits are in THIRD_PARTY_NOTICES.md and About.

The application does not install these backends automatically. It launches an explicitly chosen Python interpreter as a local subprocess, using JSON input/output and no network server. Model downloads, if any, are done by the engine itself and may contact Hugging Face. An optional engine failure does **not** replace or uninstall Chatterbox. First-time model loading can be very slow on CPU.

Qwen3 and IndexTTS have produced usable speech on the creator's Windows setup.
GPU acceleration, other hardware configurations and later upstream releases
still depend on their dependencies. These cloning engines prefer CPU and full
precision where supported. NVIDIA CUDA requires a compatible installation.

## Installing Qwen3-TTS (separate from Chatterbox)

1. Review the official [Qwen3-TTS repository](https://github.com/QwenLM/Qwen3-TTS) and its licensing, install Python 3.12.
2. From the v0.3 source root, run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\setup_qwen_windows.ps1
   ```

3. In **Voice Engines**, point **Qwen3 Python** at the interpreter printed by the script, typically `%LOCALAPPDATA%\PlaguesVoiceStudio-v030-Experimental\engines\qwen3\Scripts\python.exe`.
4. Click **Save runtime paths**, choose Qwen3, then **Test selected engine**. This validates imports, not downloading weights or inferring real speech.
5. Select a model, your existing voice reference, a reference transcript if you have one, and a test script. Generate. The Base model can use an x-vector-only speaker embedding when the transcript is omitted, but providing an exact transcript may improve similarity.

## Installing IndexTTS 2.5 (independent repository/runtime)

1. Read the [IndexTTS repository](https://github.com/index-tts/index-tts), its `LICENSE` (Bilibili Model Use License Agreement) and `DISCLAIMER`. Do not assume commercial redistribution rights.
2. Install Git and [uv](https://docs.astral.sh/uv/).
3. From the v0.3 source root, after reviewing the license, run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\setup_index_windows.ps1 -LicenseReviewed -DownloadModels
   ```

4. In Engine Lab, set both the repository directory and the `.venv\Scripts\python.exe` created under it. Click **Save runtime paths**, then **Test selected engine**.
5. Choose a reference voice, a supported language (EN, ES, JA, ZH, AR) and emotion/duration controls. The 0.5–2.0 `duration_factor` applies to IndexTTS; **greater than 1 slows speech**, unlike ordinary speed multipliers.

For either engine, installing packages or weights may require significant free disk space and virtual memory. If a library has changed its Python API upstream, the optional runner may need adjustment. This source build does not bundle independent engine wheels or weights.

## Reusable characters and comparisons

1. In **Voice Engines**, choose or type a character name (e.g., `Hattie Mama Mire Boggs`). Choose the voice reference; the stable v0.2.x library is offered read-only.
2. Pick Qwen3, its model/language/device, then **Save profile**.
3. Pick IndexTTS, configure its model/language/emotion/duration, and **Save profile** again under the **same character name**. Per-engine settings are retained in the v0.3 `character_profiles.json`.
4. Paste the same test passage, then choose **Compare Engines** (requires both configured runtimes). Results appear as individual WAVs with time measurements, descriptive filenames, and `.json` metadata. Play any result, browse it in the Export Library, or send it to the Bethesda LIP/XWM/FUZ workflow.
5. If you close the app during optional generation, it asks you to stop that work first. Cancel terminates the active engine child process. Comparisons render sequentially to limit peak memory demand.

**Important:** The Voice Engines workflow currently sends plain text directly to Qwen3 and IndexTTS. Chatterbox-specific `[pause:...]`, `[rate:...]` and vocal-event tokens are **not parsed or guaranteed** there. Use the stable Narration Studio to process those tags. No MP3 or persistent batch queue yet for optional engines. No claim of identical voice timbre or human-quality output across engines is made.

## Directory isolation

- Stable v0.2.x user data: `%LOCALAPPDATA%\PlaguesVoiceStudio-v021`, **read only** from the v0.3 build.
- Current writable data: `%LOCALAPPDATA%\PlaguedAI\apps\voice-studio`. Legacy
  app folders may be compatibility junctions after explicit consolidation.
- Character presets: `character_profiles.json`; engine settings:
  `optional_engines.json` under the current application-data folder.
- v0.1.x voices are also available read-only if present.
- New exports: `Music\Plague's Voice Studio` when Music exists, otherwise the permanent user-data `exports` folder. Older exports are still browsable.
- Previous settings registry identifier: `PlaguesVoiceStudio030Experimental`; new stable identifier: `PlaguesVoiceStudio`. Missing preferences are copied once without erasing the old registry identity.
- Existing v0.2.x Bethesda project profiles are deliberately **not modified or automatically migrated**. Create or copy mappings inside the v0.3 profile store as needed; the stable database is untouched.

## Packaging and licensing

The Windows build includes the optional runner script but **does not** bundle `qwen-tts`, `indextts`, or their model weights. The core `-FullOffline` build bundles the **four Chatterbox models only**. IndexTTS source and weights remain subject to their upstream Bilibili license, while Qwen3-TTS has separate code and model terms. PyQt6 remains subject to its GPL/commercial license. Respect speaker permission and avoid distributing third-party model assets without verifying the relevant licenses.

Before adopting a result into a production mod, compare the pronunciation, emotional delivery, consistency, artifacts, and inference time, and test any generated game-voice file in the game.

### Voice-engine diagnostics

For either engine use Voice Engines > Test selected engine, then Generate. Qwen3 0.6B Base and IndexTTS 2.5 have both produced audio on the creator's Windows setup.
A live diagnostic pane shows model import, model loading, first-time download,
CPU inference and WAV-writing stages. An elapsed clock remains visible during
long CPU generation. Press Cancel if it stalls. Probe and generation logs
are stored in `%LOCALAPPDATA%\PlaguedAI\apps\voice-studio\engine_logs`.
The core executable does not show a Python command prompt on Windows.
First-time weights can be large and need disk space. A passing import probe
only checks the engine installation, not actual synthesis.

## Running multiple local AI tools

### Windows checkpoint loading and offline tokenizer setup

The optional Qwen and Index runners use safetensors 0.8.0's `pread` reader on
Windows CPU to avoid whole-file copy-on-write mappings that can exhaust commit
memory and crash in native tensor loading. Updated setup scripts install the
required reader. Qwen reuses a complete cached snapshot by local path so its
processor does not require a remote tokenizer-metadata lookup.

Index setup applies two explicit dependency overrides to the selected upstream
checkout: safetensors 0.8.0 and OpenCV 4.12.0.88 (compatible with its NumPy 2
requirement). Only dependency declarations change; originals and SHA-256 hashes
are retained in `.pvs-windows-compat`. Fresh clones use source commit
`d9e41aac89fd00b3d71497fddb287b7f24613712`. Setup defaults to CPU wheels;
`-Backend CUDA` explicitly selects the upstream CUDA 12.8 wheel index.

Chatterbox Multilingual also requires the small Chinese segmenter and local
Cangjie mapping, even when speaking English. Model Manager reports missing
tokenizer files; choose Multilingual and Download selected model to repair them
without re-downloading complete model weights. Downloads verify a pinned SHA-256
and use normal TLS certificate validation. Generation uses local assets and
does not start a tokenizer download. New full-offline bundles include and verify
these assets; the standard slim installer keeps them in the shared model store.

The October 20 all-model Radeon retest and backend limitations are recorded in
[GPU_MODEL_AUDIT.md](GPU_MODEL_AUDIT.md). Kokoro DirectML is integrated; successful
historical native Vulkan Qwen/Index probes are separate from the Python adapters
and do not qualify the Linux source candidate below.

## Native Vulkan (Linux source candidate)

This uninstalled source candidate adds an explicit **Native Vulkan** choice for
Qwen Base 0.6B/1.7B. It uses an independently supplied audio.cpp executable,
reviewed executable hash, compatible model folder and existing coordination lock.
It does not install or redistribute that runtime, download weights, select this
backend automatically, or fall back to Python/CPU after a Vulkan failure.

Use an authorized reference excerpt of at most 30 seconds. Qwen uses the exact
matching transcript when supplied; otherwise it records embedding-only
conditioning. References are never silently shortened, and the original remains
unchanged. Engine paths, character profiles, original/prepared text and effective
backend provenance are retained separately. Discovery suggests retained local
paths only on request; saving them is explicit. Persona-plugin pronunciation and
pacing overrides are not imported into ordinary narration.

Successful output requires a consistent physical device-0 declaration and the
required Qwen model-buffer placement on Vulkan0. Software ICDs, missing identity,
conflicting device reports and required CPU buffers fail visibly. This verifies
the reported weight buffers; preprocessing or other operations may still use CPU.
Provenance labels the device identity as a runtime declaration, not an independent
hardware probe. Source tests use private fixtures and do not demonstrate audio
quality, real GPU execution or performance.

**IndexTTS 2.5:** compatible native paths can be checked, but Generate is disabled
until actual placement markers and runtime behavior are qualified. Raw Python
checkpoints cannot substitute for converted native tensors. Native emotion and
duration controls remain unavailable. Python Index behavior is retained.

Chatterbox does not use this adapter. Its bundled Torch remains CPU-only; a
separate ROCm compatibility experiment is still required. Nano/Turbo do not have
a validated equivalent native reference-cloning route. The existing Kokoro ONNX
assets also do not match audio.cpp's separate GGUF format. No Linux Vulkan
support is implied for those engines.

IndexTTS and Qwen3 can compete with a running language-model writer for memory and Windows paging resources. A previous `0xC0000005` IndexTTS crash was resolved on the creator's machine after DJ Writer was closed. If generation becomes unstable, finish one AI workload before starting another. This is a practical resource workaround, not a diagnosis for every Windows access violation.

**Compatibility paths:** Existing v0.3 storage and runtime paths include `Experimental` in their names. They are retained unchanged to avoid breaking installed interpreters, checkpoints, model caches, voices and settings. The public engine status is supported; the identifier is historical.
