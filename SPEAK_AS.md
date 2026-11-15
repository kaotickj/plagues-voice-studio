# Speak As in Voice Studio

Open **Narration Studio → Reference voice → Speak as…**. Select an existing saved voice, choose a synthesis device, hold **Hold to speak** and say your line(s) naturally, then release to convert and play. No prewritten script is needed. **Save WAV…** lets you choose a permanent recording filename; **Replay last result** plays it again. **Cancel / release model / stop playback** stops owned work and releases the model.

## Defaults and controls

- **Seed-VC V1 F0-auto** is preferred when all four Seed runtime fields are configured. It converts recorded audio directly using F0 conditioning, automatic pitch-register adjustment, length adjustment 1.0, 30 diffusion steps and CFG 0.7, producing 44.1 kHz audio. It requires voiced source and reference audio; exact timing, inflection, loudness or identity preservation is not guaranteed. See [SEED_VC.md](SEED_VC.md) for the fixed profile, setup and license evidence.
- **Chatterbox direct conversion** is the next default when Seed is not configured and an executable runtime and English S3Gen weights are available. It converts the actual recorded audio into the selected reference voice without transcribing or composing a reply. Broad timing is retained in the measured fixtures, but pitch movement, loudness and other performance details can change.
- **IndexTTS transcription + re-synthesis** is an alternate, and the fallback default only if direct conversion is unavailable. It re-speaks recognized words with emotion guidance from the recording; it does not preserve the source timeline or guarantee exact words/inflections.
- **Fast English** transcription is selected when its configured local executable and model folder exist. Choose the configured Whisper multilingual option for other languages. Transcription can change words; the recognized text stays visible.
- **Fast reference (5 seconds)** is the IndexTTS default. Only the diffusion-conditioning portion of the speaker reference is shortened. Full speaker identity/style embeddings and the microphone recording used for emotion guidance remain unchanged. The original reference file is never edited.
- **Full reference (original)** restores the original conditioning length without reloading the model. An unrecognized IndexTTS diffusion interface falls back to the full reference with a visible message. Errors never silently switch the requested GPU device to CPU.
- CPU and GPU remain explicit user choices. GPU uses CUDA/ROCm according to the configured runtime. Speak As adds no temperature ceilings, power, clock, compute-unit, fan or utilization restrictions. The Linux shared lock coordinates cooperating model jobs; it does not change GPU performance settings.
- A completed model remains warm for 60 idle seconds. Recording and transcription hold it ready. Cancel, closing the dialog or changing runtime/device/engine releases it.
- The first request loads the model, and a previously unseen audio length may need additional backend initialization. Warm timing is not a real-time guarantee.

The recording limit is 20 seconds. Recording stops if the window loses focus. Capture currently requires a microphone supporting 16 kHz mono PCM16. ASR and Chatterbox requests retain the existing two-minute stage watchdog; IndexTTS retains its five-minute cold-start watchdog. Seed uses a ten-minute watchdog because cold loading and new audio shapes can take several minutes. Cancel remains available during loading and inference. Unsaved audio is temporary and removed when the dialog closes. **Save WAV…** copies the exact converted audio and matching metadata into the permanent location you choose, without overwriting an existing WAV or JSON sidecar. Saved audio remains after another take or closing Studio and appears in Export Library. The original microphone recording is not exported automatically. Direct conversion does not invent a transcript. Before discarding an unsaved result, Studio offers Save, Discard or Cancel; after that prompt, press Hold to speak again to begin a new take. Use headphones to avoid recording speaker output.

## Existing local runtimes

No model or package is downloaded by this feature. A configuration JSON may be supplied by `PVS_SPEAK_AS_CONFIG`, which takes precedence over `speak_as.json` in Studio's existing application-data directory. The dialog only reads this file; editing runtime fields is session-only.

Default application-data directory:
- Linux: `$XDG_DATA_HOME/PlaguedAI/apps/voice-studio` (normally `~/.local/share/PlaguedAI/apps/voice-studio`).
- Windows: `%LOCALAPPDATA%\PlaguedAI\apps\voice-studio`.
- Existing `PLAGUED_AI_HOME` and Studio data-directory overrides remain supported.

The JSON is an object of string values. Supported fields:

| Field | Existing local dependency |
| --- | --- |
| `seed_python` | Executable Python in the separately installed Seed-VC environment |
| `seed_repo` | Seed-VC checkout containing `inference.py` and the populated `checkpoints/` model cache |
| `seed_cache` | Writable Seed auxiliary cache root, separate from model snapshots |
| `seed_manifest` | Local pinned model/configuration manifest with file paths, sizes and SHA-256 hashes |
| `index_python` | Executable Python or isolated launcher for IndexTTS 2.5 |
| `index_repo` | IndexTTS checkout with `indextts/infer_v2_5.py` and `checkpoints/config.yaml` |
| `chatterbox_python` | Executable Python or isolated Chatterbox launcher |
| `whisper_executable` | Working whisper.cpp CLI or wrapper |
| `whisper_model` | Local whisper.cpp GGML model file |
| `fast_asr_executable` | Optional fast-English ASR wrapper |
| `fast_asr_model` | Optional local faster-whisper English model folder |
| `gpu_lock` | Existing cooperative Linux lock file (normally `/run/lock/gnb-ai-gpu.lock`) |

All four Seed fields are required to select Seed. Its dependencies remain outside the app bundle and inference uses validated local model snapshots offline. See [SEED_VC.md](SEED_VC.md) for an example and the exact reviewed dependencies.

IndexTTS's existing Engine Lab paths and Chatterbox's existing ROCm settings are used when corresponding launcher fields are absent. Do not remove runtime or model folders referenced by the configuration. The source staging utility records exact dependencies without installing or relocating them.

ROCm IndexTTS automatically materializes semantic CPU tensors before their GPU transfer, avoiding the verified mapped-checkpoint loading stall. It preserves tensor values/dtypes and restores the upstream loader after initialization; no environment toggle or package patch is required.

## Verification and platform scope

The Debian RC4 integration was checked with local transcription, repeated GPU synthesis/direct conversion, fast/full switching, reference-cache invalidation, cancellation and permanent-save lifecycle. Earlier fast-reference audio matched the reviewed sample byte-for-byte. Direct-conversion fixture duration differences were 3–16 ms, but pitch movement narrowed and a softer second line lost its loudness contrast. The alternate re-synthesis shortened one paused fixture by about 15%. These earlier RC4 host tests used generated-speech fixtures, not a natural human take. They do not establish exact cadence/inflection preservation or replace a real user microphone and listening test. No additional pitch/loudness correction was enabled for those earlier Chatterbox tests.

Separately, the selected Seed V1 F0-auto profile was tried with a user-supplied 11.6-second natural recording in the isolated runtime. Output was approximately 5 ms shorter; that does not establish exact pitch, loudness or voice fidelity. Warm conversion of an earlier repeated 4.23-second fixture took about 13 seconds, while cold and new-shape requests took minutes. No new live-microphone test was performed for that trial. Full trial scope and limits are in [SEED_VC.md](SEED_VC.md).

The production changes preserve RC4 narration and Linux Bethesda export. Linux GPU worker lifecycle is qualified here; Windows/frozen GPU lifecycle and other hardware are not established by these checks. This is an uncommitted local development build, not a published release.
