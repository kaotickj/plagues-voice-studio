# Plague's Voice Studio 0.3.0 RC1 — Release Acceptance

**Purpose:** Verify the Windows installation contains the already merged Chatterbox script-sidecar fix and that all three speech engines can recover their original input text from exports. This is a release-candidate checklist, not a claim that a Windows RC binary has already passed testing.

## Prepare

1. Preserve Plague's Voice Studio v0.2.4 and its data. v0.3.0 RC1 retains the existing v0.3 installation paths, external engine environments, and voice profiles.
2. Close DJ Writer and other large AI workloads during speech tests to avoid RAM/page-file contention, which previously interfered with IndexTTS.
3. Check out the release-candidate branch and build with `powershell -ExecutionPolicy Bypass -File .\REBUILD_ALPHA4_EXISTING.ps1` if `.venv-build` and models are already installed. For a clean build, use `powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 -Models nano`.
4. Launch **the newly built** `dist\PlaguesVoiceStudio030Experimental\PlaguesVoiceStudio030Experimental.exe` directly, rather than an old desktop shortcut. **About** must display `0.3.0rc1`.

## Required Chatterbox acceptance test

1. Open **Narration Studio**, choose a working Chatterbox model/voice, and generate this text:

   ```text
   [narration] Goodneighbor never sleeps.

   [whispering] Neither do the shadows.
   ```

2. Find the saved WAV or MP3 in the output folder. Confirm a same-stem JSON is present: `example.wav` or `example.mp3` alongside `example.json`.
3. Confirm the log displays **Saved script metadata:** followed by the actual path. The JSON must contain a top-level `text` field, **exactly** preserving the original text, blank line, punctuation and speech tags. It also retains `engine: chatterbox` and render settings.
4. Select the audio in **Export Library**. The script preview must match the JSON text exactly. Click **Copy script**, paste elsewhere, and compare.
5. Generate again with the same requested filename. The application must choose a new numbered name for **both** audio and JSON, without overwriting the first script.
6. Cancel a new narration before completion. It must not create a completed audio/JSON pair.

## Other-engine regression checks

- Qwen3-TTS and IndexTTS 2.5 must still create their WAV and matching JSON sidecars with their `text` field. Selecting either recording must preview the original text.
- Older imported recordings without a corresponding JSON must display a clear **No saved script** message, never a script from another recording.
- Speech generation, local reference voices, playback, character profiles, optional-engine settings, and Bethesda voice export must behave as before.
- Test Chatterbox WAV first and MP3 second; MP3 encoding depends on FFmpeg.

## Automatic checks

The Windows build first runs focused Chatterbox sidecar and Export Library regression tests, then performs both frozen-runtime and frozen-GUI smoke tests before packaging. The **GUI smoke test now exercises real Export Library widgets**, creates a tiny synthetic WAV and matching JSON, verifies read-only preview and clipboard copy, then verifies missing-metadata behavior. Existing Python unit tests also exercise Chatterbox render-side JSON creation, numbered exports, and cancellation using a synthetic model.

These automated checks **do not replace one real Chatterbox synthesis** on the target Windows machine. That real generation and packaging check is the release blocker.

## Release decision

**Promote RC1 to final 0.3.0 only after:** a newly rebuilt Windows executable passes its smoke tests; real Chatterbox WAV/MP3 exports have matching JSON with exact script text; the Export Library preview/copy passes; Qwen3 and IndexTTS playback/metadata still work; no installed voices or models are lost.

**Compatibility:** The word `Experimental` still appears in existing internal executable filenames and storage paths. It is retained intentionally to prevent data loss; it is not the status of the supported speech engines.
