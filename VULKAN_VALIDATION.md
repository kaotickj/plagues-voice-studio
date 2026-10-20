# Radeon Vulkan verification — October 19, 2026

Test machine: Ryzen 5 5600X, Radeon RX 7600 XT, 16,368 MiB reported VRAM.
The pinned llama.cpp b11703 Windows Vulkan runtime detects the adapter.

Initial GPU model loads failed with native access violation 0xC0000005 on both
Gemma Writer 9B and Qwen3 Instruct 4B. CPU generation succeeded. Explicit mmap,
conservative shader settings and alternate official b10000/b11748 runtimes
did not solve the failure. They were diagnostic controls, not new app defaults.

Windows registers Mirillis Action!'s Vulkan hook using the implicit layer name
`VK_LAYER_RENDERDOC_Capture`. Excluding that layer alone in a child process
allows real GPU generation with the original b11703 runtime. OBS's separate
`VK_LAYER_OBS_HOOK` can remain enabled. The shared writer runtime now appends
only `VK_LAYER_RENDERDOC_Capture` to the child's `VK_LOADER_LAYERS_DISABLE`
filters for Windows Vulkan jobs. It preserves existing filters and does not
change the parent environment, registry, driver or recording applications.
The filter mechanism is documented by the
[Khronos Vulkan Loader](https://github.com/KhronosGroup/Vulkan-Loader/blob/main/docs/LoaderLayerInterface.md#layer-filtering).

## Actual generated-text comparison

Both backends used the same respective GGUF, b11703 runtime version, synthetic
radio-repair brief, seed 731, greedy decoding, 8,192 context tokens, six CPU
generation threads and twelve prompt threads. Jobs ran sequentially and unloaded
between stages. One draft per configuration; this is an exploratory benchmark.

| Model | CPU tokens/sec | Vulkan tokens/sec | CPU total | Vulkan total |
|---|---:|---:|---:|---:|
| Gemma The Writer Mighty Sword 9B Q4 | 4.09 | 37.55 | 21.34 s | 11.72 s |
| Qwen3 4B Instruct Q4 | 9.69 | 78.95 | 7.31 s | 4.98 s |

Token-generation throughput was about 9.2× and 8.1× higher respectively.
Whole-job gains are smaller because GPU model loading takes time. Caches and
shader compilation affect loading; these results do not establish a universal
speedup, quality improvement or cross-hardware result. Slight output differences
can occur between backends even with a fixed seed. Do not combine this table
with the earlier library-context ablation as if it were one controlled trial.

Reproduce with `python scripts/benchmark_writer_vulkan.py`. Full unedited drafts,
settings, timings and native logs are retained locally under
`artifacts/vulkan-benchmark/`. The initial failing logs and isolated compatibility
probes are also retained under artifacts; generated output is not committed.

After both GPU drafts passed, DJ Writer, Promotional Writer and its interview
stage were configured for Vulkan using the shared b11703 GPU server. Original
settings were backed up under `PlaguedAI/backups/vulkan-20261019-222024/`.
The CPU runtime remains available. Use the rebuilt packages containing this
fix; older executables lack the child-process capture-layer exclusion.

This enables writing-model GPU acceleration. It does not add Vulkan to the
PyTorch speech engines. Kokoro was subsequently integrated using DirectML;
see [KOKORO_VALIDATION.md](KOKORO_VALIDATION.md) for its separate speech tests.
