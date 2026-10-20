# Kokoro speech engine validation — October 20, 2026

Added Kokoro to Voice Engines with six preset voices: Michael, Fenrir, George,
Heart, Bella and Emma. US/UK pronunciation follows the chosen voice. Profiles
retain preset, speaking speed and backend. Reference audio/transcript controls
are hidden for Kokoro because it cannot clone arbitrary reference recordings.
Existing saved voices continue to use Chatterbox, Qwen3 or IndexTTS.

The adapter uses an independent Python 3.12 environment and the already imported
INT8 model plus voice pack in the shared PlaguedAI store. No second model download
was needed. The optional setup script pins kokoro-onnx 0.6.1 and separate CPU
(ONNX Runtime 1.31.0) or DirectML (1.24.4, ONNX tools 1.23.2) environments.
DirectML includes a CPU provider for unsupported operations. Auto prefers it
when available; explicit GPU mode reports unavailability rather than silently
presenting CPU inference as GPU work. No changes to graphics drivers were made.

## Actual Radeon inference

Hardware: Ryzen 5 5600X, Radeon RX 7600 XT. The writing-model Vulkan verification
is separate: this ONNX backend uses DirectML/DirectX 12 on Windows.

The official model-files-v1.1 INT8 export initially crashed during DirectML graph
optimization. Disabling graph optimization exposed a runtime rejection of three
grouped ConvTranspose nodes with nonzero output_padding. The integration disables
that optimizer and caches an equivalent graph: output_padding is absorbed into
the right padding, only when that padding remains nonnegative. Auto-padding and
explicit output-shape cases are rejected. Original ONNX bytes and all learned
tensors remain unchanged. The derived graph adds about 114 MB to the shared
store, keyed by source SHA-256 and transformation version; cache contents are
hash-verified and replaced atomically. CPU uses the original graph.

Twelve independent CPU operator comparisons across groups and input lengths
passed with maximum absolute error **0.0**. They also verify unchanged initializer
tensors, unchanged original bytes and cache reuse. Reproduce with the separate
DirectML interpreter and `scripts/validate_kokoro_directml_graph.py`.
The full ONNX checker reports an existing Loop subgraph ordering issue in the
upstream export; the rewrite preserves the same issue. Actual ONNX Runtime
inference works. Operator parity does not establish identical audio samples
across CPU and GPU; backend arithmetic and model randomness can vary.

All six voices then rendered real speech through Studio's request/subprocess/
sidecar protocol using DirectML. Output is non-silent mono PCM16 at 24 kHz.
Each profiled sample recorded more than 6,200 DirectML execution events, plus
CPU events for unsupported operations. This is real GPU inference, not only
successful adapter enumeration.

| Voice | Render seconds | Audio seconds |
|---|---:|---:|
| Michael | 7.02 | 13.30 |
| Fenrir | 6.67 | 11.72 |
| George | 6.31 | 12.45 |
| Heart | 6.33 | 11.75 |
| Bella | 6.33 | 12.11 |
| Emma | 6.33 | 11.04 |

Times include process/model loading and profiling. Earlier CPU runs took about
33–37 seconds for the same passage. CPU and DirectML use different ONNX Runtime
versions, and the GPU graph has the equivalent padding rewrite; this is a local
backend comparison, not an isolated hardware benchmark. One passage per voice
does not establish general quality or speed. A separate speed=1.25 CPU render
shortened Michael's output from 13.34 to 10.96 seconds.

Unedited WAVs, exact text, timing/RMS measurements, backend/provider metadata and
native ONNX profiles are in `artifacts/kokoro-gpu-validation/`; earlier CPU output
is in `artifacts/kokoro-validation/`. Failed native probes and the minimal-graph
control are retained under artifacts. Reproduce actual GPU samples with
`python scripts/validate_kokoro.py --device directml --profile`.

## Application checks and packaging

Request, runtime-isolation, no-overwrite and Qt profile/control tests cover
reference-free generation, preset/accent validation, GPU options, explicit
unavailable-backend errors and restoring cloning controls after switching engines.
Source GUI smoke passes, including both existing plugins and Kokoro controls.
Final packaged checks and regression counts are recorded in BUILD_VALIDATION.md.
The rebuilt EXE's explicit `--kokoro-self-test <report.json>` also passed actual
DirectML synthesis from the frozen host process, recording 4,363 GPU events.
The final portable is `artifacts/kokoro-host/PlaguesVoiceStudio-Kokoro-Portable.zip`.
No public release or new commit is implied by these local validation records.
