# Radeon model audit — October 20, 2026

Follow-up: the Python Qwen/Index/Multilingual failures recorded below were
subsequently repaired and passed real CPU synthesis. See
[SPEECH_LOADING_VALIDATION.md](SPEECH_LOADING_VALIDATION.md). The original failed
audit attempts remain intact as historical evidence.

Actual inference on the local **Radeon RX 7600 XT, 16 GB**, Ryzen 5 5600X,
48 GB RAM. The Radeon works with substantially more of this library than the
current CPU/CUDA speech selectors expose. GPU availability and a successful
import were not counted as successful model inference.

## Results and application integration

| Installed model/component | Radeon result | Current application status |
|---|---|---|
| Gemma Writer 9B Q4 | Vulkan text generation passed | Shared DJ/Promo writer runtime supports Vulkan |
| Qwen3 Instruct 4B Q4 | Vulkan text generation passed | Shared writer runtime supports Vulkan |
| Imported Ollama Gemma3 1B, Gemma3 4B, Qwen3 0.6B | All three passed Vulkan text generation | Tested through private llama.cpp instances; does not change the apps' selected model |
| Gemma3 4B vision projector | Vulkan image description passed | Separate multimodal probe; no new image UI |
| Qwen3-TTS Base 0.6B and 1.7B | Both passed Vulkan reference-conditioned synthesis | Native audio.cpp probes; Studio's Python adapter remains CPU/CUDA |
| IndexTTS 2.5 | Vulkan reference-conditioned synthesis passed | Native audio.cpp probe; Studio's Python adapter remains CPU/CUDA |
| Kokoro INT8 | All six presets passed DirectML synthesis again | Integrated and rebuilt in Studio, including explicit CPU/DirectML choices |
| ACE-Step 1.5 Turbo Q8 and SFT Q8 | Both passed Vulkan music synthesis | Separate ace-synth probes |
| ACE-Step 5Hz LM 0.6B Q8 | Passed Vulkan generation of music codes used in both synth runs | Separate ace-lm probe |
| Qwen3 Embedding 0.6B Q8 and ACE-Step VAE BF16 | Both exercised successfully in both Vulkan music synth runs | Components of the separate ACE-Step probe |
| BART large CNN, all-mpnet-base-v2, all-MiniLM-L6-v2 | All three passed CPU and DirectML inference | Isolated test environment, no application backend replacement |
| Chatterbox English and Multilingual v3 | Native Vulkan port failed; low-memory retries failed; native English CPU control also failed | Requires further port/memory work |
| Chatterbox Nano and Turbo | CPU synthesis passed; no compatible reference-cloning Vulkan adapter validated | Installed Python engines remain CPU/CUDA |

The tested audio.cpp release has no Nano adapter. Its community Turbo path uses
a baked preset rather than this Studio's reference-cloning workflow, so that
path was not presented as a successful test of the installed Turbo model.
MiniLM's cached ONNX optimization/CPU-architecture exports are formats of the
same model; those individual exports were not independently validated. The
underlying cached MiniLM weights were tested with PyTorch DirectML.

## Actual outputs and timings

The five text models completed in 7.72, 3.51, 9.16, 13.17 and 4.80 seconds in
the table's order. These include model loading. Gemma Writer's unedited output:

> It's late, the mood is mellow, and Goodneighbor Blues is your soundtrack. Stay tuned for soulful sounds all night long.

The Gemma vision run used the existing application icon, loaded the projector
through the Vulkan backend and completed an image-conditioned response. Native
logs include `CLIP using Vulkan0 backend` and completed image decoding.

| Speech/music probe | Total seconds, including loading | Output seconds |
|---|---:|---:|
| Qwen3-TTS 0.6B | 23.86 | 2.72 |
| Qwen3-TTS 1.7B | 24.34 | 2.48 |
| IndexTTS 2.5 | 43.50 | 4.50 |
| Kokoro Michael, latest retest | 6.69 | 13.30 |
| ACE-Step Turbo | 22.97 | 9.44 |
| ACE-Step SFT | 14.91 | 9.44 |

Qwen and Index used a ten-second excerpt of the existing Johnny Watts reference
and the text: `Good evening. You're listening to Goodneighbor Blues.` Their
logs place model buffers on Vulkan0. Index logs identify model variant 2.5.
Kokoro profiles record thousands of DirectML events plus CPU fallback events.
Both music clips are stereo 48 kHz instrumental blues; the separate music LM
stage took 8.28 seconds. These short probes establish execution, not a ranking
of quality, clone fidelity, pronunciation or general performance.

All **14 produced WAVs** from the final successful audit cases decoded to
nonempty, finite, non-silent audio. No speech-recognition transcript comparison
or listening-quality acceptance is implied. Original audio, exact text, timings,
RMS, logs and GPU evidence are retained under `artifacts/gpu-model-audit/`.

Small embedding batches did not benefit from GPU transfer/setup overhead:
MPNet took 0.125 seconds on CPU versus 0.188 on DirectML; MiniLM took 0.031
versus 0.187. BART took 2.531 versus 1.594 and produced the same summary text.
These are single short inference measurements excluding weight loading, not
controlled throughput benchmarks. A CPU option remains useful.

## Why the current engines miss Radeon

The installed Studio, Qwen and Index environments contain **CPU PyTorch builds**
(2.6.0+cpu, 2.14.1+cpu and 2.8.0+cpu respectively). Their device selection checks
`torch.cuda.is_available()` and otherwise uses CPU. These installations expose
neither HIP nor Vulkan. Adding `vulkan` to a dropdown cannot supply missing
operators, model execution graphs or runtime libraries.

[PyTorch's Vulkan documentation](https://docs.pytorch.org/tutorials/unstable/vulkan_workflow.html)
states that its old Vulkan backend is no longer maintained and was not included
by default. It points to ExecuTorch's Vulkan delegate. This is separate from the
working ggml/llama.cpp Vulkan implementations tested here. Native model adapters
are a practical route, as the Qwen, Index and ACE tests demonstrate.

[AMD's Windows ROCm 7.2.1 PyTorch matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityrad/windows/windows_compatibility.html)
does not list this RX 7600 XT/gfx1102. This concerns that published PyTorch
support matrix, not all AMD HIP SDK support or the hardware's ability to run
Vulkan. No driver, system paging or global environment changes were made.

[DirectML supports PyTorch on Windows](https://learn.microsoft.com/en-us/windows/ai/directml/pytorch-windows),
but the tested `torch-directml 0.2.5.dev240914` package requires PyTorch 2.4.1.
It was installed in a separate probe environment, without downgrading working
speech runtimes. The three NLP models work there using `torch.no_grad()`;
`torch.inference_mode()` exposed a DirectML version-counter restriction.
Kokoro uses ONNX Runtime DirectML and its separately validated graph fix; see
[KOKORO_VALIDATION.md](KOKORO_VALIDATION.md).

A separate source of native Vulkan crashes was the Mirillis Action! implicit
capture layer. The writer runtime and these Vulkan probes exclude only
`VK_LAYER_RENDERDOC_Capture` in their child environment. Other capture layers,
registry values and global environment settings remain unchanged.

## Chatterbox failure diagnosis

The tested audio.cpp Chatterbox port reserves **4096 MiB** for T3 weight metadata
while reporting about **0.096 MiB used** there, plus several further large
metadata arenas. Those reservations consume Windows commit even when learned
tensors are stored on the GPU. The low-memory/q8 retries reached about
11.4 GiB of private process memory with only 0.9–1.0 GiB of available system
commit, then failed to allocate an additional 413–423 MiB Vulkan buffer during
T3 prefill. The matching native English CPU control also failed a 423 MiB
allocation after its further metadata reservation. Execution-job memory limits
were checked and were zero; the test shell did not impose a 12 GB process cap.

The evidence supports a port allocation/Windows commit-pressure failure.
It does **not** establish that Chatterbox cannot run on Radeon. Reducing the
port's oversized metadata arenas and retesting is still required before exposing
it as a reliable Studio backend. No third-party source patch or replacement
Chatterbox build is included in the current app package.

## Additional Python baseline findings

Installed Python Nano, Turbo and English Chatterbox rendered audio on CPU.
The Multilingual baseline could not obtain a missing Chinese segmenter asset
because the upstream GitHub download failed certificate verification. The
forced-offline Qwen 0.6B baseline hit a tokenizer metadata network lookup;
Qwen 1.7B and Index's Python baselines hit native access violations while
loading Hugging Face model tensors. These failures are retained and are not
counted as passes or attributed to Vulkan. Their causes need separate follow-up;
the native Vulkan probes of the same Qwen/Index checkpoint families passed.

## Reproduction and provenance

The audit scripts are `retest_shared_text_gpu.py`, `probe_gemma_vision_vulkan.py`,
`probe_native_speech_vulkan.py`, `probe_acestep_vulkan.py`,
`probe_cached_nlp_directml.py` and `retest_installed_speech_cpu.py` in `scripts/`.
Run the NLP script with the isolated `torch-directml-probe` interpreter, one
model per process. Run heavy model jobs sequentially. The collection script
`collect_gpu_model_audit.py` reads existing results and checks decoded WAVs.

Writer tests use llama.cpp b11703. Native speech uses
[audio.cpp](https://github.com/0xShug0/audio.cpp) release
`v0.9.2-drama3-base-small`, source commit
`507495611b22dc4590e0e5609e05e8096384e33f`.
Downloaded release ZIP SHA-256:
`9c943d406af3543cc5005d158ed583210cd7a13371bffcd4b7f262f7a6a5ad16`.
ACE binaries report `de858d8 (2026-10-16)` and came from the developer's HTTPS
download linked in upstream documentation; local hashes are recorded, but no
publisher checksums were supplied for those binaries.

Existing weights remain in the shared PlaguedAI store. Native staging uses NTFS
hardlinks for unchanged files; separate converted Index/MTL tensors and the
Kokoro compatibility graph require additional storage. Originals were preserved.
Runtime versions, hashes, checkpoints and individual failed attempts are in
`artifacts/gpu-model-audit/`; `summary.json` collects final result sets and audio
checks. Large models, audio and runtime archives remain local ignored artifacts.

No commit, push, public release or additional installer was produced for this
audit. The existing Kokoro portable contains its integrated DirectML adapter;
successful native Qwen/Index probes do not enable those backends in Studio yet.
