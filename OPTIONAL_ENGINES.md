# Speech engines: Qwen3-TTS and IndexTTS 2.5

**Baseline:** Plague's Voice Studio v0.2.4 remains unchanged. The separate v0.3.0 build retains the four Chatterbox models in **Narration Studio** and supports both Qwen3-TTS and IndexTTS 2.5 through **Voice Engines**. Real speech generation with both has been confirmed on the creator's Windows machine. Keep independent engine runtimes out of `.venv-build` and the PyInstaller distribution folder.

## Engine status and requirements

| Adapter | Functional interface | Requirements | Verified here |
| --- | --- | --- | --- |
| Qwen3-TTS | 0.6B Base and 1.7B Base choices, reference-voice cloning, English and 9 other languages, WAV | Separate Python 3.12, `qwen-tts`, model weights (download on first use) | Windows CPU speech generation confirmed with 0.6B Base; 1.7B not separately confirmed |
| IndexTTS 2.5 | Reference-voice cloning, five languages, optional emotion vector, duration factor, WAV | Separate `uv` environment, official `index-tts` checkout and `checkpoints/` weights | Successful Windows speech generation confirmed by the creator |

The application does not install these backends automatically. It launches an explicitly chosen Python interpreter as a local subprocess, using JSON input/output and no network server. Model downloads, if any, are done by the engine itself and may contact Hugging Face. An optional engine failure does **not** replace or uninstall Chatterbox. First-time model loading can be very slow on CPU.

Both engines have produced usable speech on the creator's Windows setup. GPU acceleration, other hardware configurations and later upstream releases still depend on their dependencies. Defaults prefer CPU and full precision where supported. NVIDIA CUDA requires an independently compatible installation.

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
- v0.3 legacy data: `%LOCALAPPDATA%\PlaguesVoiceStudio-v030-Experimental` (retained read-only after copying portable data). New writable data: `%LOCALAPPDATA%\PlaguesVoiceStudio`.
- Character presets: `%LOCALAPPDATA%\PlaguesVoiceStudio\character_profiles.json`; engine settings: `optional_engines.json` under the same stable root.
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
are stored in `%LOCALAPPDATA%\PlaguesVoiceStudio-v030-Experimental\engine_logs`.
The core executable does not show a Python command prompt on Windows.
First-time weights can be large and need disk space. A passing import probe
only checks the engine installation, not actual synthesis.

## Running multiple local AI tools

IndexTTS and Qwen3 can compete with a running language-model writer for memory and Windows paging resources. A previous `0xC0000005` IndexTTS crash was resolved on the creator's machine after DJ Writer was closed. If generation becomes unstable, finish one AI workload before starting another. This is a practical resource workaround, not a diagnosis for every Windows access violation.

**Compatibility paths:** Existing v0.3 storage and runtime paths include `Experimental` in their names. They are retained unchanged to avoid breaking installed interpreters, checkpoints, model caches, voices and settings. The public engine status is supported; the identifier is historical.
