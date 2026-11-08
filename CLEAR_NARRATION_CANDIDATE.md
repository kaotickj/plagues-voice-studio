# Clear Narration candidate — 2026-10-25

Local candidate branch: `codex/clear-narration`, based on the preserved release
audit at `2ca0f765b6c88a38d662e872d47b9012b08ffe4c`. That base includes two
existing audit fixes after public main `5b3ed5e7a811e7950820359a3b91ce45dcb810aa`.
Remote main was checked with a read-only `git ls-remote` on 2026-10-25.

## Bounded first slice

- **Current settings** remains the default. **Clear Narration** is an opt-in,
  reproducible general-use starting point: temperature 0.8, expressiveness 0.5,
  CFG 0.5, 220-character chunks and 180 ms inter-segment gaps. Custom values are
  retained when changing profiles and when reopening the candidate.
- CFG and expressiveness generation controls are visibly unavailable for
  Turbo/Nano and are absent from their generation arguments. The existing
  reference-preparation exaggeration argument is recorded separately.
- **Preview render plan** reviews the current render text, exact segments and
  effective settings without loading a speech model. It can be opened with
  `Ctrl+Shift+P`. Generate and queue snapshot the current editor and controls.
- **Selected passage** renders only the explicit selection into a separate
  export. Select complete passages including surrounding app directives;
  incomplete styles are rejected. This does not splice new audio into an older
  recording. **Full document** remains available.
- The manuscript is preserved. JSON sidecars distinguish original manuscript,
  prepared render input, render scope, voice ID, effective settings, actual
  generation arguments and render plan. Export Library displays render input
  and original manuscript in separate read-only views.
- No vocal events or persona are inserted. Explicit user-written tags remain.
  Reference conditioning is prepared once per job, reset before preparing a
  new voice, and reset after preparation failure. A missing selected reference
  fails instead of silently selecting a built-in voice.

This profile uses documented general-use settings; it is not a new model,
trained voice, or demonstrated audio-quality improvement. Pronunciation &
Script Prep continues to provide its reviewed dictionary/normalization workflow.
Shared core pronunciation profiles, reference transcripts for Qwen, optional
engine instruction support and automatic audio assembly are outside this slice.

## Research and local verification

[Original Chatterbox guidance](https://github.com/resemble-ai/chatterbox#original-chatterbox-tips)
supports CFG/exaggeration for the original model. The local adapter excludes
those generation controls for Turbo/Nano. Shorter chunks can change transitions;
they are a prompt budget rather than a quality guarantee.

[Qwen's Base clone API](https://github.com/QwenLM/Qwen3-TTS#voice-clone) accepts a
reference transcript or an explicit embedding-only mode. The local runner uses
those paths and does not consume Speech Director instruction metadata.
[Index's API](https://github.com/index-tts/index-tts#-python-api) defines
`duration_factor > 1` as slower speech. The local runner/UI use that direction
and one selected fixed-strength emotion vector, not exported per-segment vectors.
Speech Director changes no weights: its Chatterbox export inserts synthesis
tags, while Qwen/Index directions remain metadata until an adapter consumes them.

## Verified installation and preserved work

Installed Debian package: `plagues-voice-studio 1.0.0~rc1-1`, executable
`/usr/lib/plagues-voice-studio/PlaguesVoiceStudio030Experimental`. Its build
manifest records source `e07bbf8362d14dcd3d7c78feb78a69949bbd022e`, Python 3.12.15,
Torch 2.6.0+cpu and Chatterbox 0.1.7. Executable SHA256:
`4cfa499945024a0f48776e148f6f39fcb88f4d2b09ee6b808df1aa58f3411e25`.
Frozen internal module equivalence with newer source was not established;
13 compared standalone runner/plugin files match the newer audit checkout.

The clean older `~/git/plagues-voice-studio`, newer release-audit checkout, and
dirty build checkout under `~/Documents/Codex/builds/plagues-voice-studio` were
preserved. The dirty checkout contains unfinished DJ Writer/Linux/Ollama work.
No private session logs were read. No project-specific AGENTS or .agents skill
instructions were found beyond the workspace handoff instructions.

Existing Chatterbox weight directories were observed, without integrity or
inference checks. Configured Qwen interpreter points to a Windows-mounted JSON
file and needs correction before use; Index paths are blank. Kokoro paths and
model/voice-pack files exist. These facts do not establish runtime readiness.
The reported Radeon accelerator has not been benchmarked with this candidate.
About 39 GB storage was available; the planned additional SSD was not present.

## Validation boundary

Software tests use a Python 3.13 harness assembled from existing local test
dependencies, fake speech models, temporary settings/data and hidden GPU
devices. This is distinct from the supported Python 3.11/3.12 packaged runtime.
Qt profile/preview tests use real widgets with inert media objects
because desktop audio initialization is unavailable in the task sandbox. The
synthetic speaking-rate test uses real existing FFmpeg with a runner-only
executable-discovery shim; it does not establish packaged dependency readiness.
Detailed pass counts and evidence are reported with the candidate handoff.

The final bounded suite passed **110 tests**: legacy/profile settings,
serialization, exact preview/render plans, selected passages, word preservation,
pronunciation preparation, voice isolation, cancellation, sidecars, acceptance
request forwarding and real Qt widgets. Independent defect review reported no
findings. Default 1330×880 and minimum 940×650 layouts were visually inspected,
including scrolling to export/effective-settings controls and keyboard preview.
Local evidence is retained in `test-evidence/`: `independent-final.xml`,
`independent-software.log`, `independent-environment.json`, screenshots and the
reproducible `run_software_checks.py` runner. Those machine-specific artifacts
are not part of the source commit.
After the last missing-reference refresh fix, the **18 UI/acceptance checks**
were rerun and passed; their separate reports are in
`test-evidence/reference-followup/`.

Real synthesis, latency/memory measurement, packaged-build testing and listening
acceptance remain pending. When coordinated after Broadcast's priority work,
compare one bounded passage with the same authorized voice/model/text using
custom baseline versus Clear Narration. Check omissions, repeats, pronunciation,
intelligibility, pacing, identity and unwanted effects. Preserve both exports and
their sidecars; no new model download is required by this candidate.

No running application, voice, model, user audio or user settings was replaced.
No model downloads, training, paid services, credentials/security changes,
pushes or GitHub Actions runs were performed. Linux workflow is manual-only;
Windows workflow still builds matching source pushes to main/develop/release
branches or version tags. Pull requests targeting main/develop also trigger
Bethesda regression jobs. Any later push/build requires release or major-test
coordination under the user's cost restriction.
