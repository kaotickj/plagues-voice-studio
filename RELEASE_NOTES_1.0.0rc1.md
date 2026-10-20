# Plague's Voice Studio 1.0.0rc1

This is a **release candidate**, not the final stable 1.0 release.

## Changes

- Shared `%LOCALAPPDATA%\PlaguedAI` model, runtime and reference-voice storage,
  with compatibility discovery for existing installations. Writer and speech
  tools can reuse existing assets without downloading another copy.
- Radeon Vulkan support in the shared DJ/Promotional Writer runtime. The tested
  Mirillis capture-layer conflict is avoided only in owned compute subprocesses.
- Kokoro speech with six preset voices, speed controls and optional Radeon
  DirectML inference. Kokoro uses fixed presets and does not clone reference audio.
- Windows CPU checkpoint loading uses bounded safetensors reads for Qwen/Index,
  and complete cached Qwen installations no longer require a remote tokenizer
  metadata lookup. Updated optional setup scripts apply tested dependencies.
- Model Manager can repair missing Multilingual tokenizer assets with a verified
  download. Multilingual generation uses local mapping/segmenter files.
- Pronunciation & Script Prep plugin, reusable advertiser profiles/interviews,
  separate writing/interview models and configurable CPU thread budgets.
- Windows GUI packages include GPL v3 binary-distribution notices and source
  directions; original application source files retain MIT licensing.

- Generic **Plugins → Promotional Writer**: spoken ads, promotional spots,
  announcements, product descriptions, social posts, taglines and custom prompts.
  Local Gemma/Qwen writing models remain separate from speech engines. Reviewed
  text can be sent to Narration Studio, with confirmation before replacing a
  script. The branded Goodneighbor DJ standalone is not bundled.
- Fixed update discovery rejecting normal version numbers. Alpha/beta/RC tags
  cannot be offered as stable updates even if their release metadata is wrong.
- Windows optional-engine cancellation now stops the owned interpreter tree,
  including child Python processes, instead of leaving model memory/log handles
  alive after a venv launcher exits.
- Pinned the validated Windows CPU dependency/toolchain snapshot and upstream
  commits. Builds run the complete regression suite before packaging. Frozen
  runtime, GUI/plugin and installed-application checks gate release publishing.
- Reconciled obsolete engine-support/model-location assertions. Kept the existing
  application identity, executable name and stable user-data paths for upgrades.

## Installation and models

The standard package is model-on-demand: speech and writer model weights are
not embedded in the installer. Chatterbox uses Model Manager. Qwen3-TTS and
IndexTTS retain independently configured Python runtimes. Promotional Writer
can reuse existing writing-model paths without copying weights or DJ profiles.

The Windows build uses CPU PyTorch. Writer Vulkan support depends on the selected
llama.cpp runtime and hardware. Run memory-heavy AI jobs sequentially.

## Candidate acceptance still required

- Test the newly installed candidate with your real voice library and configured
  Chatterbox, Qwen3-TTS and IndexTTS runtimes. Historical engine success on an
  earlier build is not a new candidate inference result.
- Both Qwen3-TTS model sizes, IndexTTS 2.5 and Multilingual Chatterbox have
  completed actual CPU synthesis with the repaired source adapter. Packaged
  acceptance records are tracked separately in BUILD_VALIDATION.md.
- IndexTTS first-time installation still uses the documented advanced setup;
  a complete graphical dependency/model installer is not included in this RC.
- Bethesda export has automated container/conversion/handoff coverage. Real
  FaceFX/xWMA tools and in-game audio/lip-sync acceptance remain unverified here.
- Review distribution/model terms and final release assets before declaring GA.
  A prerelease is intentionally not offered by the stable-update checker.

Native Vulkan Qwen/Index and ACE-Step tests are diagnostic experiments; those
backends are not exposed as supported Voice Studio engines in this RC.
DJ Writer remains a separate standalone download, outside the generic host.

See `RELEASE_READINESS.md` for measured validation and remaining gates.
