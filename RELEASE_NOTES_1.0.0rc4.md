# Plague's Voice Studio 1.0.0rc4

RC4 adds an explicit external AMD ROCm route for Original English Chatterbox on
Linux, persistent processor/runtime controls, and clearer model/runtime setup.
The bundled host PyTorch remains CPU-only; GPU generation requires a separately
configured compatible runtime. Chatterbox is not presented as a Vulkan engine.

The shared narration workflow preserves original manuscript separately from
prepared render text and effective settings. Optional Natural Narration keeps
the listener-preferred CFG 0.3 starting point for Original English without
changing legacy defaults or unsupported models. Clock-time preparation handles
valid a.m./p.m. expressions without rewriting arbitrary colon expressions.
Optional native Vulkan menus are separate from the Chatterbox ROCm route.

## Actual qualification

- Original English Chatterbox completed real AMD GPU speech, including reference
  conditioning and vocoder execution. The creator accepted the Plague audition.
- The creator verified that settings persisted after closing and reopening the
  installed application, and approved the reviewed README/wiki drafts.
- IndexTTS 2.5 was installed in a separate Linux Python 3.11.17 environment with
  Torch 2.8.0+rocm6.4. Verified model files and offline frontend/import checks
  passed. The actual installed Studio adapter produced a 4.226-second Mama
  Mire-reference WAV with observed GPU forwards through BigVGAN. The creator
  listened and accepted that exact sample.
- The cold, instrumented Index test took 119.66 seconds overall, with peak process
  RSS 8.70 GiB and peak Torch GPU allocation 6.04 GiB. These results demonstrate
  execution; they do not establish a speedup or universal acoustic improvement.

## Installation and limitations

Use the Windows x64 setup EXE or Debian amd64 DEB attached to this release,
after checking the matching SHA-256 manifest. Portable packages are separate
assets. Source archives are not installers. The local Debian build's glibc
baseline is recorded in its BUILD-INFO.json; do not assume older Linux support.
Packages omit model weights and optional external Python runtimes.

See [detailed IndexTTS installation](INDEXTTS_INSTALLATION.md) for Windows/Linux
Python versions, official source/model pins, backend differences, paths and
troubleshooting. Fresh Windows setup of the pinned Index revision has not been
qualified; historical Windows speech is separately identified in the guide.

AMD support remains experimental and specific to the tested stack. Nano,
Turbo, Multilingual Chatterbox GPU generation, Qwen speech on this Linux stack,
and optional native Vulkan generation have not been qualified by these tests.
Index native Vulkan remains disabled. GPU alone does not improve model quality.
Kokoro preset voices do not clone reference recordings.

Linux provides ordinary WAV/MP3 workflows; production Bethesda LIP/XWM/FUZ tools
remain Windows-only and require separately supplied tools. Real game/tool
acceptance is not claimed. Installers are unsigned.

Existing Linux and Windows reference registries can differ. Historical Windows
exemplars were located; no automatic voice consolidation or source-drive repair
is performed by this release. Preserve current settings, references and original
audio, and retain a known installer for rollback before changing versions.

Final Windows installer checks, Linux package checks, asset names/digests and
upload state must be verified before this release is made public. At preparation
time, no RC4 public release or successful final CI run is claimed.
