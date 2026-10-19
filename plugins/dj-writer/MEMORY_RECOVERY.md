# Memory allocation and recovery (AI Studio v0.8.3)

These changes affect only the **local llama.cpp text writer**, not Plagued Voice Studio's speech engines. No model download or data migration is needed.

## What the October 16 crash logs show

- Gemma The Writer 9B initially failed when allocating an approximately 3.71 GiB `CPU_REPACK` buffer. The v0.8.2 `--no-repack` option addresses this specific allocation.
- At 23:41:53, Gemma instead failed at `failed to allocate buffer for kv cache` while allocating about 756 MiB.
- At 23:42:22, Qwen3 4B failed to allocate a roughly 2.25 GiB KV-cache buffer. This proves that smaller model *weights* alone are not a complete workaround.
- Some logs contain only an initialization line; those logs do **not** prove success or failure.
- The messages about `</s>` being overridden are not the fatal error.

## New AI Setup controls

- **Disable weight repacking:** default on. Appends `--no-repack`.
- **KV-cache memory:** default **Balanced** (`--cache-type-k q8_0 --cache-type-v f16`). Reduces key-cache memory and keeps value-cache precision at F16. **Standard** uses F16 for both. **Compact** uses Q8 for both and explicitly enables Flash Attention; compact compatibility depends on the runtime and compute backend.
- **Automatic recovery:** default on. On an actual KV-cache allocation failure, close the private server, then restart with smaller contexts from the user's configured size down through 16,384, 8,192, 4,096, 2,048, and 1,024 tokens as applicable.
- **Context tokens:** the editor now accepts values down to 1,024. For diagnosis, manually try **4,096** (or **2,048** for a short commercial) to avoid repeated retries. Larger contexts are needed for long scripts.

A successful fallback reports the context used and does not overwrite the saved configuration. If that context cannot fit the requested prompt and target output, the writer fails visibly **before generation**, instead of silently truncating a long story. Already completed drafts are preserved if a subsequent attempt fails.

## Windows troubleshooting if 4,096 still fails

1. Use Task Manager, Performance > Memory, and inspect **Committed** (in-use / limit). Memory allocation can fail with physical RAM still free if the Windows commit limit is reached.
2. Check the Windows page-file configuration. System-managed virtual memory is often appropriate; do not disable the page file just because you have plenty of RAM.
3. Close concurrent AI servers, TTS models, browsers, and GPU-heavy tasks; retry one writer process.
4. Compare the CPU and Vulkan writing backends if your installed llama.cpp runtime supports them. This application does not claim either path has been validated on your Windows GPU.
5. If even 1,024 context tokens fail, capture the *newest* server log and Task Manager's committed-memory figures. Do not assume thread count is the cause.

## Safety and compatibility

- All launches remain localhost-only and authenticate with an ephemeral API key.
- This change does not install or update GGUFs, override profile/continuity data, or change the speech-engine targets.
- The automatic retry applies **only** to the specifically recognized KV-cache allocation failure, not to malformed weights, unsupported command-line flags, or backend errors.
- Changing CPU thread count improves or worsens inference *speed* depending on the system, but does not cure these startup allocations.
- This release passed 36 non-GUI unit tests locally. It has not been run with a real Windows `llama-server`, GGUF model, or Qt GUI in this environment.
