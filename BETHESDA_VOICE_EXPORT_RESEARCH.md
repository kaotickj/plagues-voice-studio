# Plague's Voice Studio: Bethesda voice pipeline research

**Status:** Technical background from v0.1.4-preview, incorporated into the independently packaged v0.2.1 source. **Not yet verified in Fallout 4 or Skyrim inside the game.** For current installation paths and profile behavior see README.md and [BETHESDA_LINUX.md](BETHESDA_LINUX.md). The November 2026 update below supersedes the historical Windows-only validation limits.

## Confirmed architecture

1. The Chatterbox synthesis stage produces a WAV or MP3 master recording; it retains all existing narration functionality.
2. `Bethesda Voice Export` is an additional tab. It uses an *existing* recording and a plain spoken transcript with tags removed. It never re-renders the speech.
3. Prepares 16 kHz mono 16-bit PCM WAV for FaceFXWrapper, then passes the game's **own LIP profile**. FO4 uses `Fallout4`, Skyrim and Skyrim SE use `Skyrim`.
4. Prepares 44.1 kHz mono 16-bit PCM WAV for xWMA encoding. Uses a user-supplied `xwmaencode.exe` or the MIT `WMAEncodeRS.exe`. The latter is recommended for redistribution planning, but is *not bundled* here.
5. Packs the `.fuz` in our own audited Python code. Its format is `FUZE` + little-endian uint32 version (1) + uint32 lip size + LIP bytes + encoded audio bytes. Round-trip unpacking verifies our output.
6. Creates `Data/Sound/Voice/<YourMod.esp>/<VoiceType>/<ResponseFilename>.fuz` in a staging directory. Source WAV/LIP/XWM and transcript are kept separately in `PVS_Source_Files/` if requested. Do not include this backup directory in your shipped mod.

**Naming caveat:** Actual dialogue filenames must match Creation Kit dialogue response exports exactly. The UI lets users enter the filename but cannot derive it reliably without the plugin and CK-export metadata. Replacing an existing FUZ requires confirmation and an external backup.

The October 17, 2026 code review tightened container validation, output publication,
transcript handoff and saved VoiceType selection. See
[BETHESDA_RELEASE_CHECK.md](BETHESDA_RELEASE_CHECK.md) for the remaining real-tool
and in-game acceptance test. Automated tests use real FFmpeg but simulated
FaceFX/encoder output; they do not establish native LIP generation or playback.

## Tools and licensing

| Part | Candidate | Redistribution decision |
| --- | --- | --- |
| Audio preprocessing | FFmpeg via existing `imageio-ffmpeg` | Included in existing dependency; preserve applicable FFmpeg and build licensing notices |
| XWM encoder | https://github.com/MSIVST/WMAEncodeRS | MIT Rust source; encodes RIFF/xWMA with Windows codecs; check license notice and Windows Media runtime conditions before bundling the compiled EXE |
| Alternative XWM | xwmaencode.exe supplied by Bethesda Creation Kit | User installs official CK; **do not redistribute Bethesda's tool without permission** |
| LIP generation | https://github.com/Nukem9/FaceFXWrapper | Source repository is MIT-labelled but explicitly includes/depends on CK-derived material and Fonix data, covered by Bethesda licensing. **User-supplied binary only** pending license review |
| Fonix | `FonixData.cdf` from installed CK | Bethesda data; **never bundle** |
| FUZ | Local `bethesda_export.py` | Native Python packing, no external binary needed |
| Experimental alternative LIP | https://github.com/OpenFaceFX/OpenFaceFX | MIT clean-room Skyrim writer, but **not yet in-game verified**; FO4 LIP unsupported; do not market as production ready |
| Official FO4 alternative | Creation Kit `-GenerateLips:<Plugin>` | FO4 August 18, 2026 CK patch fixed command-line LipGen; plugin-level batch workflow should be a later integration path |

A game-independent approach isn't correct: Fallout 4 `.lip` differs from Skyrim `.lip` (see xVASynth `.lip`/`.fuz` plugin documentation).

## Known constraints and validation plan

- The preview was tested with **synthetic stand-in tools** and structural FUZ round-trip tests. A passing mock encoder proves packaging code, **not in-game compatibility**.
- xWMA must be real RIFF/xWMA data, not MP3 or plain WAV with a changed extension. Source audio remains archival; the encoded XWM and lip data are packaged for the game.
- The transcript should reflect *actual spoken words* including any unexpected model deviations. Nonverbal utterances can affect synchrony.
- `FaceFXWrapper` may fail on particular Creation Kit builds; use its 6-argument (already resampled WAV) mode. Capture errors and leave no false `.fuz` successes.
- A user should produce a 1–2 sentence test in each game: verify audible dialogue, mouth animation, subtitle alignment, playback length, and proper archive deployment. Repeat with a different NPC voice type.
- Batch metadata import from CK and automated creation of game plugins/BA2 archives are not part of this preview.
- This feature requires working external Windows tools. The historical preview did not test them on Windows; the November 2026 update below records a real Wine experiment separately.
- Fallout 4's August 2026 CK patch mentions FUZ with embedded WAV for **PlayStation Creations**; do not assume that allowance applies to standard PC xWMA workflows.

## Documentation / sources reviewed

- https://github.com/Nukem9/FaceFXWrapper
- https://github.com/MSIVST/WMAEncodeRS
- https://github.com/OpenFaceFX/OpenFaceFX
- https://openfacefx.com/docs/COMPATIBILITY/
- https://openfacefx.com/docs/api/exporters/
- https://www.nexusmods.com/skyrimspecialedition/mods/55605
- https://help.bethesda.net/app/answers/detail/a_id/72995/
- https://github.com/RLR64/Robo-Voice-Pipeline
- https://github.com/charlestietjen/fallout4-revoiced-tool

## Next release milestones

1. Test **actual Windows FaceFXWrapper + FonixData + xWMA** on FO4 and SSE voice sample quests; capture reference fixture FUZ files.
2. Import CK-exported dialogue metadata for correct FormID/Response/VoiceType filenames, batch manifest and automatic queue creation.
3. Expose optional official CK `-GenerateLips:` fallback for supported versions; implement test discovery and caching to avoid reencoding unchanged dialogue.
4. Package Windows distribution only after full third-party license audit and side-by-side game tests.


## November 8, 2026: Linux implementation and dependency review

The Linux route uses a selected Wine executable and already initialized dedicated
prefix, with path translation through that same Wine's `winepath.exe`. Native
FFmpeg prepares audio. The official Fallout 4 `LipGenerator.exe` backend is
restricted to Fallout 4; FaceFXWrapper retains the `Skyrim` / `Fallout4` profiles.
Native Windows execution is preserved. Conversion of existing audio does not
need a GPU or acquire the narration synthesis lock. Setup is documented in
[BETHESDA_LINUX.md](BETHESDA_LINUX.md), not an unattended third-party installer.

### Official acquisition and license evidence

- Upstream [FaceFXWrapper release 0.41](https://github.com/Nukem9/FaceFXWrapper/releases/tag/0.41)
  was published December 8, 2021. The official release API identifies
  [FaceFXWrapper.0.41.zip](https://github.com/Nukem9/FaceFXWrapper/releases/download/0.41/FaceFXWrapper.0.41.zip)
  (28,206,543 bytes). A local inspection download had SHA-256
  `e3ab949456b6a24d31de24616a4f9131f5d66be00c8b8b867cf64cb173d8f9f9`.
  This is an observed hash, not a publisher signature or independent authenticity
  guarantee. The ZIP contains `Tools\Audio\FaceFXWrapper.exe` (34,387,456 bytes)
  and `Tools\Audio\README.txt` (752 bytes), no `FonixData.cdf`.
- The [MIT license](https://github.com/Nukem9/FaceFXWrapper/blob/master/LICENSE.md)
  applies alongside the [README's explicit restriction](https://github.com/Nukem9/FaceFXWrapper#license):
  CK-derived code remains subject to Bethesda's agreement and compressed resources
  are Bethesda property. This review established an official acquisition source,
  not blanket compiled-binary redistribution rights. The archive README itself
  warns about unvalidated LIP correctness and identifies Fonix as proprietary.
- [WMAEncodeRS LICENSE](https://github.com/MSIVST/WMAEncodeRS/blob/main/LICENSE)
  is MIT, crediting original WMAEncode and its Rust port. Its
  [README](https://github.com/MSIVST/WMAEncodeRS) identifies the Windows Media
  runtime dependency. That source license does not convey redistribution rights
  to Microsoft codecs or prove the encoder functions under Wine.
- No proprietary converter or Fonix resource was added to the source tree or
  application package in this work. A locally acquired tool is not a bundled
  deliverable. Revisit compiled-tool distribution only with applicable rights
  and retained license/provenance evidence for that exact artifact.

### What the previous bundle evidence actually establishes

The standard source/package configuration at baseline `e07bbf8` was inspected,
including `ChatterboxStudio.spec`, `installer.iss`, `scripts/`,
`BINARY_LICENSE.md`, `THIRD_PARTY_NOTICES.md` and `BUILD_VALIDATION.md`.

- The Windows spec collects `imageio_ffmpeg`, including its executable. The
  binary license records imageio-ffmpeg 0.6.0's unmodified Windows FFmpeg 7.1
  essentials executable from Gyan, with GPL/version-3 configuration, provenance,
  source revision and license directions. Redistributable tooling **was** part
  of that Windows bundle; it is incorrect to say no third-party tools shipped.
- The Linux spec deliberately excludes imageio's FFmpeg executable while keeping
  its Python wrapper. Linux uses the distribution's FFmpeg package instead.
- The inspected spec has no explicit FaceFXWrapper, Fonix, xwmaencode or
  WMAEncodeRS collection; no corresponding binary is tracked in the baseline
  tree. The binary notice explicitly excludes FaceFXWrapper and Bethesda assets
  from the standard slim host; third-party notices also mark WMAEncodeRS external.
- Inno Setup recursively copies the prepared distribution directory. Therefore
  the source/spec alone is **not** a forensic inventory of every historical
  installer, a manually supplemented portable directory or a custom earlier
  bundle. The actual previous artifact manifest and its license records are
  needed to settle those contents. Do not remove previously verified components
  or describe them as forbidden merely because this working tree excludes them.

These findings preserve the distinction between known redistributable components,
unknown historical bundle contents, and unverified rights to the proprietary
parts of FaceFXWrapper. They do not replace a release-specific compliance audit.

### Real-tool evidence, separate from acceptance

After the preliminary standalone experiment, the actual `export_dialogue` API
passed a real-tool Fallout 4 export on Debian 13 using GE-Proton11-11's Wine and
a freshly initialized dedicated prefix. It generated fresh LIP and xWMA,
atomically installed FUZ into staging, verified an exact container round trip,
and decoded non-silent 44.1 kHz mono audio of the expected duration. Paths with
spaces were exercised. No game installation or existing game prefix was changed.
See [BETHESDA_LINUX_VALIDATION.md](BETHESDA_LINUX_VALIDATION.md) for the exact
outputs, repeatable script and negative controls; measured LIP sizes can vary
between fresh runs, so no deterministic-output claim is made.

The initial standalone negative control with nonexistent WAV returned exit code
zero without output. Fresh output validation therefore must not rely on tool
exit codes alone. Regression results are recorded in
[BETHESDA_RELEASE_CHECK.md](BETHESDA_RELEASE_CHECK.md). Neither container checks
nor decoded audio establish in-game facial animation. FaceFXWrapper subsequently
passed actual API export for Fallout 4, Skyrim and Skyrim SE with the runtime
completion below. Native Windows and WMAEncodeRS runtime remain unvalidated.

### FaceFXWrapper 0.41 mapping-failure follow-up

An initial Wine invocation of official 0.41 failed with
`Failed to map CK executable into memory`. The failure was subsequently resolved
in the tested GE-Proton11-11 environment as described below. Source inspection
at tag 0.41 explains the initial failure boundary:

- [Loader.cpp](https://github.com/Nukem9/FaceFXWrapper/blob/0.41/FFXW32/Loader.cpp),
  `MapExecutable`, chooses the embedded `CK_LIP_BINARY` resource for the game,
  decompresses it and calls `MemoryLoadLibraryEx`. The reported error is emitted
  when that call returns null. It does not search for an installed CK executable
  relative to cwd or the wrapper location. Its memory layout uses fixed x86
  image addresses; nonblacklisted imports use `LoadLibraryA`.
- [FFXW32.cpp](https://github.com/Nukem9/FaceFXWrapper/blob/0.41/FFXW32/FFXW32.cpp)
  processes CLI paths directly. Only the separate `Ckpid`-selected IPC mode uses
  the hardcoded relative output `Data\Sound\Voice\Processing\Temp.lip`.
- [CreationKit32.cpp](https://github.com/Nukem9/FaceFXWrapper/blob/0.41/FFXW32/CreationKit32.cpp)
  explicitly patches the embedded engine's Fonix data path to the supplied
  command-line value. Therefore a scratch cwd and absolute Wine-mapped inputs
  remain appropriate for Studio's CLI integration. Do not infer a required game
  installation mutation from the release archive's `Tools/Audio` layout note.
- [MemoryModule.c](https://github.com/Nukem9/FaceFXWrapper/blob/0.41/dependencies/MemoryModule.c)
  can fail for image validation, memory allocation, imported DLL/function lookup
  and other loader conditions. The observed top-level message does not identify
  which one occurred. Diagnose the Wine trace before prescribing runtime changes.

The supported strategy is an external user-supplied wrapper, correctly selected
game/Fonix paths and isolated work files; clear inherited CK IPC selection for
CLI execution. Do not copy or replace game CK files as a speculative fix. The
working official Fallout 4 backend remains an alternative for that game only.


### Verified GE-Proton11-11 runtime completion and final result

Wine loader diagnostics identified missing `libvkd3d-1.dll`,
`libvkd3d-shader-1.dll` and `libvkd3d-utils-1.dll` in its graphics import chain.
Six files already provided by the **same installed GE build**, under
`files/share/default_pfx/drive_c/windows/{system32,syswow64}`, were copied into
the matching folders of the new disposable prefix. `WINEDLLPATH` alone did not
resolve the failure; the successful copy-only run needed no environment overrides.
This was not a download of foreign DLLs or a change to a game/system prefix.

After that setup, actual `export_dialogue` calls passed for FaceFXWrapper's
Fallout 4, Skyrim and Skyrim SE selections, plus official Fallout 4 LipGenerator.
Every result had fresh LIP, valid xWMA, exact FUZ round trip and non-silent decoded
audio. The supported Python 3.12.14 run and specific output measurements are in
[BETHESDA_LINUX_VALIDATION.md](BETHESDA_LINUX_VALIDATION.md). The final aggregate
regression run passed **335 tests, with 1 skipped**. Manual runtime instructions
are in [BETHESDA_LINUX.md](BETHESDA_LINUX.md); Studio does not silently copy DLLs.

This validates those export combinations on that runtime, not in-game facial
animation, universal Wine/Proton compatibility or a new right to redistribute
proprietary FaceFXWrapper resources. Keep the per-game in-game acceptance gate.
