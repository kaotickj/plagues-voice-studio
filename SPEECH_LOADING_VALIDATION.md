# Windows speech release-blocker repair — October 20, 2026

The installed Python Qwen3-TTS 0.6B, Qwen3-TTS 1.7B, IndexTTS 2.5 and
Chatterbox Multilingual v3 now complete actual CPU speech generation from the
repaired source adapter. These are the Python engines used by the application,
separate from the experimental native Vulkan probes in GPU_MODEL_AUDIT.md.

## Checkpoint and offline processor loading

Qwen 1.7B and Index failed in native tensor loading through safetensors memory
mappings. On Windows CPU, the optional job process now uses safetensors 0.8.0's
bounded `pread` backend before engine/Transformers imports. No learned tensors,
model files, drivers, system paging settings or host PyTorch packages changed.
The change is restricted to the optional engine subprocess; CUDA and other
platforms retain their original reader. Setup reports a clear requirement for
older environments instead of attempting the known failing CPU path.

This matches the Windows mapping/commit-pressure failure described in
[Transformers issue 48285](https://github.com/huggingface/transformers/issues/48285).
The prior native traces and successful same-checkpoint read-backend trials
support the diagnosis; not every Windows access violation has this cause.

Qwen's upstream processor invokes a tokenizer metadata lookup despite cached
weights. A complete local snapshot is now passed by directory, including the
speech tokenizer and processor files. Both models rendered with
`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`; incomplete snapshots retain the
normal missing/download behavior. No remote lookup is needed for a complete
installation.

Qwen's measured environment: qwen-tts 0.1.1, Transformers 4.57.3, PyTorch
2.14.1+cpu, safetensors 0.8.0. Its setup pins the tested integration packages.
Index source revision: d9e41aac89fd00b3d71497fddb287b7f24613712, PyTorch
2.8.0+cpu, Transformers 4.52.1. Its explicit Windows compatibility helper updates
only safetensors 0.5.2 → 0.8.0 and OpenCV 4.9.0.80 → 4.12.0.88 dependency
declarations (the latter matches upstream's NumPy 2 requirement). The original
project file and before/after hashes are retained. Refreshing editable metadata
then passed dependency consistency with no inference source changes. Fresh setup
defaults to CPU wheels; CUDA is an explicit alternative. A fresh full Index
environment bootstrap is separate from the repaired installed-environment test.

## Multilingual tokenizer assets

Upstream initialization tried to download its Chinese segmenter even for English
generation and failed certificate verification. Its Cangjie loader also ignored
the already downloaded local JSON. Model Manager now installs the segmenter
explicitly, verifies upstream archive SHA-256 and both member hashes, rejects
unexpected archive members, supports cancellation and repairs assets without
re-downloading complete model weights. An actual fresh helper download passed
with normal TLS verification. No certificate checks are disabled.

Generation supplies the local segmenter directory and Cangjie mapping while
retaining upstream tokenization behavior. The temporary constructor override is
locked and restored on errors. Missing files produce a Model Manager repair
instruction. Slim installers exclude these weights; full-offline setup downloads
and verifies them. Frozen packaging explicitly collects spacy-pkuseg and srsly,
whose import from compiled feature-extractor code escaped ordinary module analysis.

## Actual source inference

All cases used the same ten-second Johnny Watts reference and script:
`Good evening. You're listening to Goodneighbor Blues.`

| Engine | Total seconds including loading | Audio seconds | Sample rate |
|---|---:|---:|---:|
| Qwen Base 0.6B | 100.11 | 8.40 | 24,000 |
| Qwen Base 1.7B | 65.66 | 3.04 | 24,000 |
| IndexTTS 2.5 | 213.64 | 8.94 | 22,050 |
| Chatterbox Multilingual v3 | 85.17 | 3.96 | 24,000 |

Each output is finite and non-silent, with its output script saved beside the
WAV. These are execution checks, not listening-quality or clone-fidelity ratings.
The same installed checkpoints were reused. Jobs ran sequentially.

Host regression suite after the repairs and explicit frozen speech checker:
**287 passed, 1 skipped**, including the native process-tree cancellation test.
The source and frozen inference tests are deliberately separate: an early fresh
EXE caught the missing srsly packaging dependency despite source success.
Final packaged results, installer acceptance and package hashes belong in
BUILD_VALIDATION.md and artifacts/release-ready-rc1/; a successful source render
alone does not establish packaged acceptance.

Private evidence: artifacts/release-speech-repair/ (requests, unedited audio,
logs, environment versions, dependency check, live download, unit results).
`scripts/test_frozen_speech.ps1` runs explicit offline inference against the
rebuilt EXE and checks audio and exact saved script metadata. It never runs
automatically at application startup.
