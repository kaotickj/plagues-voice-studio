# Shared Plagued AI storage

All applications use `%LOCALAPPDATA%\PlaguedAI` by default on Windows.
`PLAGUED_AI_HOME` can override the shared root. Custom Studio/DJ data-home
overrides remain supported for isolated acceptance tests and portable projects.

```
PlaguedAI/
  models/text/                 Gemma and Qwen writing GGUFs
  models/chatterbox/           speech checkpoints by model variant
  models/index-tts/2.5/         IndexTTS checkpoints
  models/huggingface/          shared Hub cache, including Qwen3-TTS
  models/music/ace-step-1.5/   imported music-generation GGUF components
  models/speech/kokoro/       ONNX speech weights and stock voice pack
  models/ollama/              text-model blobs and original Ollama manifests
  runtimes/llama.cpp/          versioned CPU/Vulkan writing runtimes
  downloads/llama.cpp/         verified runtime archives
  voices/                     imported voice reference audio
  voices.json                 shared voice names and persistent IDs
  apps/voice-studio/           Studio state, plugin profiles, logs, projects
  apps/dj-writer/              standalone DJ profiles, history and libraries
```

Speech and writing models are different assets: Qwen3-TTS cannot substitute
for Qwen3 Instruct. Distinct architectures, quantizations and model revisions
are never treated as duplicates just because their names resemble each other.
The Promotional Writer's writing and interviewing stages share these model
files while retaining their separate settings. Script Prep needs no model.

Writer downloads use cross-process file locks so two tools cannot write the
same partial model at the same time. Existing presets are verified by size and
SHA-256 before reuse. Existing user-selected custom paths remain supported.
Runtime variants stay separate, but each can be reused by all writers.

## Existing installations

Close Studio, DJ Writer and model servers before applying migration. The scripts
below audit by default. They do not download models.

1. `python scripts/consolidate_voices.py` audits every known voice index.
   `--apply` consolidates audio, validates SHA-256, preserves IDs (including
   `legacy:`/`stable:` references), and leaves old audio-folder junctions.
2. `python scripts/consolidate_ai_storage.py` audits existing model, cache,
   runtime and application-state folders. `--apply` renames them on the same
   volume and leaves compatibility junctions. Conflicting destinations abort;
   the script never merges over another installation. Failed link creation
   rolls the current folder rename back. Earlier completed steps are journaled.
3. `python scripts/deduplicate_ai_models.py` compares large models by SHA-256.
   `--apply` atomically replaces only byte-identical copies with hard links.
   Model files must be treated as immutable; never edit checkpoint bytes in place.

Migration reports are stored under the shared root. The full Hugging Face cache
is relocated intact, preserving other cached repositories and the old cache
path via a junction. Installed speech-engine Python environments stay where
they are: their packages/scripts may contain absolute paths. IndexTTS accesses
its consolidated checkpoints through the old-path junction or a shared fallback.

Old folder names can still appear in Explorer. A junction is an alias, not a
second copy. Do not delete these aliases until older builds and saved absolute
paths no longer need them. Voice audio is consolidated, while original indexes
remain available for older applications. New builds use the shared index.

Fresh DJ installs copy portable legacy state only; they never copy models or
Python environments. Fresh Studio installs similarly migrate prior portable
state without copying heavy assets. Existing complete models are discovered
before downloading. If upgrading another machine, run the explicit consolidation
tools before launching the new builds to get the same fully shared layout.

## Local acceptance, October 19, 2026

Consolidated 11 registered voices from three libraries, preserving all referenced
audio and IDs. Relocated eight existing storage trees on the same volume and
verified old-path aliases. Deduplicated 12 identical model files, reclaiming
14,461,454,924 bytes (about 13.47 GiB). No distinct model was removed. Installed
engine environments remain at their original paths. Reports contain the hashes
and source/destination paths; private voice/profile data is not committed.

## Server model import

Copied and SHA-256-verified all nine installed models plus Kokoro's voice pack
from `10.0.2.12` to this Windows machine (`10.0.2.16`): five ACE-Step-related GGUF
components (Turbo, SFT, 5Hz LM, Qwen embedding and VAE); Kokoro INT8 plus its voice
pack; and the original Ollama stores for Qwen3 0.6B, Gemma3 1B and Gemma3 4B.
There are 26 distinct files including shared blobs and manifests, totaling
11,751,793,844 bytes. Copies match the server SHA-256 values. No server model,
service or file permission was changed.

`scripts/import_server_models.py` audits by default and supports explicit
`--apply`, resumable partial files and hash verification. It checks the vault and
standard local Ollama/LM Studio locations for identical files before copying.
The current transfer found no identical versions there; similar model family
names do not mean identical weights. An already-generated inventory can be
reused with `--inventory artifacts/server-model-import/inventory.json`; every
copied file is still verified. The script uses existing SSH authorization and
does not copy private keys. Its temporary server identity path must still exist
for a later run, or the SSH configuration must be adapted to current access.

The previously empty default `~/.ollama/models` now aliases
`PlaguedAI/models/ollama`, allowing a local Ollama installation to reuse the
copied manifests/blobs. `OLLAMA_MODELS` can also point at this shared directory.
This copy does not install Ollama or ACE-Step execution backends. Kokoro is now
available through Voice Engines with separate DirectML and CPU runtimes under
`runtimes/python/kokoro-directml` and `runtimes/python/kokoro-onnx`. Both reuse the
copied model/voice pack. DirectML caches one padding-compatible ONNX graph under
`models/speech/kokoro/directml`; this preserves the original weights and adds
about 114 MB, shared across tools, rather than separate copies per application.
Kokoro's six exposed stock voices are separate from the eleven imported
reference recordings; it cannot clone them. Music/ASR engines still need their
own integration. See [Kokoro setup](OPTIONAL_ENGINES.md#kokoro-preset-voices).

Both current desktop writing models have verified Radeon Vulkan generation;
see [VULKAN_VALIDATION.md](VULKAN_VALIDATION.md). Kokoro speech has verified Radeon
DirectML generation; see [KOKORO_VALIDATION.md](KOKORO_VALIDATION.md). The existing
PyTorch speech engines keep their configured backends. Shared weights are never
bundled into the slim installers.
