# DJ Writer 0.9.3

This standalone update enables the shared Vulkan writing backend and reuses
models/runtimes in `%LOCALAPPDATA%\PlaguedAI`.

- Fixes native Vulkan model-loading crashes caused by the Mirillis Action!
  implicit capture layer. Only owned Vulkan subprocesses exclude that layer.
- Gemma Writer 9B and Qwen3 Instruct 4B generated real text on the RX 7600 XT.
  Measured token throughput improved substantially; whole-job speedups vary.
- Preserves advertiser libraries, curated Fallout references and accepted DJ
  character notes. CPU generation and separate writing/interview models remain
  available; heavy model stages run sequentially.
- Provides a Windows installer, portable ZIP and SHA-256 manifest. Existing
  model files can be reused; weights/runtimes are not embedded in these packages.
- Includes Windows binary license notices and corresponding-source directions.

Vulkan accelerates inference; it does not improve the underlying model's writing
ability or train it from use. Saved references provide bounded context, and
generated copy still needs editorial review. Speech-engine Vulkan integration
is separate from this writer update.

Validation includes 148 regression tests, frozen startup/icon checks, actual
GPU text generation and isolated installer upgrade/reinstall/uninstall tests.
See VULKAN_VALIDATION.md and BUILD_VALIDATION.md in the source repository.
