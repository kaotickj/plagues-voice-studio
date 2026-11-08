# Bethesda export release check

This check covers the desktop application's existing WAV → LIP + XWM → FUZ
workflow. The application does not create or edit plugin dialogue records.

## Linux integration, November 8, 2026

Linux supports an explicitly selected Wine executable and initialized dedicated
prefix; native Windows execution remains available. The official CK LipGenerator
backend is limited to Fallout 4. FaceFXWrapper retains game-specific profiles
but is experimental/runtime-dependent on Linux. Fresh Linux settings choose
LipGenerator + CK xwmaencode; legacy saved FaceFX paths and explicit choices are
preserved. Setup checks are read-only configuration checks, not tool execution.
The Linux tab includes a bundled read-only dependency guide with user-clicked
HTTPS source links, plus cancellation and per-tool timeouts.

**Real-tool API result:** `export_dialogue` passed on Debian 13 using GE-Proton11-11
Wine, a fresh disposable prefix and official Fallout 4 tools. Fresh output,
FUZ round trip, xWMA decoding and paths with spaces were checked. See
[BETHESDA_LINUX_VALIDATION.md](BETHESDA_LINUX_VALIDATION.md) for exact evidence,
FaceFXWrapper results, failure controls and the opt-in repeat script.
[Setup instructions](BETHESDA_LINUX.md) cover Debian dependencies and acquisition.

FaceFXWrapper 0.41 also passed actual API exports for Fallout 4, Skyrim and
Skyrim SE after six matching VKD3D DLLs from the installed GE build's default
prefix were copied into the disposable test prefix. No extra environment
overrides were needed. Studio does not install/copy that optional runtime setup.

**Final aggregate regression:** Python 3.12.14, **335 passed, 1 skipped** in 16.12 s.
The real-tool report identifies the tested backend hash; regressions and actual
conversion are separate checks. No native Windows runtime or in-game acceptance
is claimed by these Linux tests. The historical October results below remain
dated evidence, not the current suite total.

## Code review fixes, October 17, 2026

- Reject incomplete RIFF/xWMA files, missing audio/seek chunks, PCM disguised as
  XWM, and malformed FUZ containers before installing or replacing source files.
- Check that resampling produced nonempty 16 kHz / 44.1 kHz, 16-bit mono WAVs.
- Save the output script in new Qwen3/IndexTTS metadata and load the selected
  recording's script when handing it to Bethesda Export. Older files without
  output text clear the previous transcript; paste and review their actual words.
  The reference speaker transcript is never substituted for the output dialogue.
- Clear the previous project's VoiceType when changing projects or deleting an
  assignment, while retaining a VoiceType being entered when saving its project.
- Reject reserved Windows filenames, avoid filesystem writes during destination
  previews, and report project-directory errors through the GUI.
- Keep conversion consoles hidden on Windows and prevent a newly appearing target
  from being overwritten without permission. Publication uses a unique temporary
  file in the destination directory.

## Automated verification

Run `python -m pytest -q`. The export tests invoke real FFmpeg on a synthetic
stereo 24 kHz recording and check the actual resampled WAVs. They cover Fallout 4,
Skyrim, and Skyrim SE selections; both encoder argument formats; game Data and
MO2 roots; failed tools; broken output; overwrite backups; concurrent target
creation; and Qt transcript/project handoffs.

FaceFX and encoder output in these tests is simulated. The xWMA fixture has a
valid container structure but no real compressed speech; it cannot validate
audio decoding or lip animation. The `Bethesda export regression tests` workflow
runs these focused tests on Windows and Linux without downloading TTS models.

Local audit result (Linux, Python 3.12, October 17, 2026): **144 tests passed**,
including **85 focused export/handoff tests**. The full application's source Qt
smoke test also passed. These results do not include real Windows FaceFX or
xWMA encoding, a rebuilt Windows executable, or an in-game session.

## Windows and in-game acceptance

Use the rebuilt application containing these fixes. For each game advertised as
verified, use a dialogue response already configured in that game's Creation Kit.

1. Select your installed **FaceFXWrapper**, **FonixData.cdf**, and either
   **WMAEncodeRS** or **Creation Kit xwmaencode**. External tools remain
   user-supplied. FaceFX currently uses its `USEnglish` profile, so use English
   dialogue for this check.
2. Generate one or two spoken sentences with a working engine. Send the result
   to Bethesda Export and check that the transcript matches the audible words.
   For recordings without saved script metadata, paste the matching transcript.
3. Select the correct game, owning plugin filename, VoiceType EditorID, and
   **exact response filename from the Creation Kit**. The application cannot
   infer the required response basename from an audio file or NPC name.
4. Select the game's existing **Data** folder, or an existing **MO2 mod root**.
   Confirm the preview ends in
   `Sound/Voice/<Plugin.esp>/<VoiceType>/<Response>.fuz`.
   A MO2 mod root must not add another `Data` folder.
5. Build the package. The destination should contain the FUZ. If source retention
   is selected, WAV/LIP/XWM/transcript files go into the current application's
   `bethesda_source/<Plugin>/<VoiceType>` project directory. Existing v0.3
   installations retain `%LOCALAPPDATA%\PlaguesVoiceStudio-v030-Experimental`.
6. Trigger that exact dialogue in the game. Check the correct actor/voice,
   complete audio, mouth movement throughout the line, approximate alignment
   with spoken words, and the end of the line. A successful file export alone
   is not the in-game acceptance result.
7. Repeat with another generated line. Test an overwrite once: decline to verify
   the original remains, then accept and verify the previous FUZ appears in
   `bethesda_source/<Plugin>/<VoiceType>/backups`.
8. Record game version, engine/model, converter versions, response filename,
   elapsed export time and audible/lip-sync results. Only mark games and encoder
   combinations actually tested as verified.

Useful upstream references:

- [FaceFXWrapper arguments and input WAV format](https://github.com/Nukem9/FaceFXWrapper)
- [WMAEncodeRS xWMA output and bitrate units](https://github.com/MSIVST/WMAEncodeRS)
- [Microsoft RIFF audio loading](https://learn.microsoft.com/en-us/windows/win32/xaudio2/how-to--load-audio-data-files-in-xaudio2)
