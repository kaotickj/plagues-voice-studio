# Plague's Voice Studio 1.0.0rc1

This is a **release candidate**, not the final stable 1.0 release.

## Changes

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
- Qwen3-TTS 1.7B cache checks were reported successful; its actual candidate speech
  generation has not yet been verified.
- IndexTTS first-time installation still uses the documented advanced setup;
  a complete graphical dependency/model installer is not included in this RC.
- Bethesda export has automated container/conversion/handoff coverage. Real
  FaceFX/xWMA tools and in-game audio/lip-sync acceptance remain unverified here.
- Review distribution/model terms and final release assets before declaring GA.
  A prerelease is intentionally not offered by the stable-update checker.

See `RELEASE_READINESS.md` for measured validation and remaining gates.
