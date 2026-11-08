# Linux Bethesda export validation

## Scope and result (2026-11-08)

**PASS:** the actual `export_dialogue` API produced fresh LIP, encoded xWMA,
and atomically installed FUZ for official Fallout 4 LipGenerator and
FaceFXWrapper 0.41 Fallout 4, Skyrim, and Skyrim SE modes on Debian 13.
No game directory or existing game Wine prefix was modified.

**Not validated:** playback or animation in a running game, native Windows
execution, or other Wine distributions. FaceFXWrapper required the installed
GE-Proton vendor DLL preparation described below; plain `wineboot` alone failed.

Environment:

- Debian GNU/Linux 13, x86_64, Linux 6.12.113, glibc 2.41.
- GE-Proton11-11-x86_64's `files/bin/wine`, reporting Wine 11.0 (Staging).
- System FFmpeg; locally supplied official Fallout 4 `LipGenerator.exe`,
  `FonixData.cdf`, and `xwmaencode.exe`.
- A **new disposable prefix**, initialized with that exact Wine executable.
- Final validation: supported **Python 3.12.14**. Earlier exploratory tests used
  Python 3.13.5 for the standard-library backend only, not full application support.
- Source recording: 16.4 seconds, matching dialogue text supplied locally.
  Neither recording nor proprietary tools are included in the repository.

## Actual API and data checks

The latest successful run used backend SHA-256
`27173b3ca0826ff79d54b24bd8c7220e648a1915dad83dd829eb99996fb44f4b`.
The official Fallout 4 backend produced:

| Check | Observed result |
| --- | --- |
| Fresh LIP | 23,318 bytes; first header uint32 = 1 |
| xWMA | 102,818 bytes; backend RIFF/xWMA validator passed |
| FUZ | 126,148 bytes, version 1 |
| Container round trip | Extracted LIP and XWM exactly equal retained sidecars |
| FFmpeg decode | 16.439727891 seconds, 44.1 kHz mono PCM |
| Decoded signal RMS | 3165.651 on signed 16-bit scale, nonzero |
| Duration difference | Approximately 0.040 seconds |
| Paths with spaces | Prefix, staging mod, sidecars, and scratch paths exercised |
| Cleanup | Temporary export/tool-log directories removed |

FaceFXWrapper completed the same API and validation checks for all three modes:

| Mode | LIP bytes | FUZ bytes |
| --- | ---: | ---: |
| Fallout 4 | 22,276 | 125,106 |
| Skyrim | 22,472 | 125,302 |
| Skyrim SE | 23,546 | 126,376 |

Each contained 102,818-byte XWM, decoded to the same 16.439727891-second audio
and nonzero RMS above, round-tripped exactly, and removed scratch directories.

The script asserts output did not exist beforehand and its modification time is
new. Each generation uses fresh scratch paths. An earlier independent fresh-prefix
run also passed, producing a 21,319-byte LIP. LIP generation was not byte-for-byte
deterministic across runs; no deterministic or animation-quality claim is made.

## Failure and atomicity checks

These call `export_dialogue` with real harmless local test processes in place of
the Windows LIP tool. They test the shared process/export failure path, **not**
Wine process-tree cancellation itself:

- Exit-zero `/bin/true` produced no LIP: rejected as missing fresh output.
- A sleeping local process exceeded a one-second timeout: rejected in 1.108 s.
- Cancellation while that process was running: cancelled in 0.407 s.
- All three preserved an existing destination file byte-for-byte with overwrite
  enabled, left no `.partial`/`.pvs-partial` files, and removed scratch directories.

## FaceFXWrapper evidence

Initially, the executable from the official Nukem9 FaceFXWrapper 0.41 release
ran under a plain wineboot-created prefix but exited 1. Direct execution revealed:

> Failed to map CK executable into memory

The release source embeds its Creation Kit payload (`CK_LIP_BINARY`), then maps
that payload in memory. This failure therefore does **not** demonstrate a missing
installed Creation Kit executable, and copying one beside the wrapper is not a
justified remedy. The release README's game-directory layout refers to its CK
integration usage. Source:
<https://github.com/Nukem9/FaceFXWrapper/blob/0.41/FFXW32/Loader.cpp>.

A scoped Wine `+module,+seh` diagnostic showed missing `libvkd3d-shader-1.dll`,
`libvkd3d-utils-1.dll`, and `libvkd3d-1.dll` imports for `wined3d.dll`, followed by
`dxgi.dll`/`d3d11.dll` load failures. The selected installed GE-Proton distribution
already provides these files in its own default prefix.

**Verified remedy, isolated test prefix only:** copy these three files from each
of `files/share/default_pfx/drive_c/windows/system32` and `syswow64` under the
selected GE-Proton installation into the matching directories of the newly
created dedicated prefix. Six files total, both architectures, no replacements
of existing files. No additional download, DLL override, `WINEDLLPATH`, or
`LD_LIBRARY_PATH` change was needed for the successful full API run.

Setting the vendor's `WINEDLLPATH` alone had failed. Copying only the six vendor
files succeeded for every tested mode. This is a narrowly tested GE-Proton layout,
not a universal Wine repair. No system/game prefix was changed. Follow
`BETHESDA_LINUX.md` for the optional dedicated-prefix preparation procedure.

Wine printed missing-FreeType diagnostics in this environment. The official
Fallout 4 pipeline nevertheless completed successfully. Those warnings alone
were not the reason FaceFXWrapper failed.

## Repeat the opt-in real test

Run only with tools you are entitled to use. The script creates a fresh prefix
and leaves isolated artifacts for inspection; allow sufficient temporary disk
space for Wine initialization. It does not install or download dependencies.

```sh
python3 scripts/validate_bethesda_linux.py \
  --wine /absolute/path/to/wine \
  --tools '/absolute/path/to/official tools' \
  --source '/absolute/path/to/dialogue.wav' \
  --text-file '/absolute/path/to/matching dialogue.txt'
```

The tools directory must contain `LipGenerator.exe`, `FonixData.cdf`, and
`xwmaencode.exe`. FFmpeg defaults to `/usr/bin/ffmpeg`; override with `--ffmpeg`.
Optionally supply `--facefx /absolute/path/to/FaceFXWrapper.exe` to probe that
backend with the selected runner. For the tested installed GE-Proton layout, add
`--proton-default-dlls` to copy the six vendor DLLs into the **new test prefix
only**. The script requires all source files to exist, refuses to overwrite an
existing destination DLL, and records source hashes. It never downloads DLLs. The script then attempts Fallout 4, Skyrim,
and Skyrim SE separately, records individual failures, and returns nonzero if
any requested case fails. The generated `validation.json` contains environment
and observed checks; it does not embed the source dialogue text.

The command prints its disposable artifact root. Inspect results and remove only
that generated directory afterward if no longer needed. Never substitute a game
prefix or a game installation directory for test output.

## RC4 integration and preservation

Before installation, the feature was integrated with current main
`6d52d85d04406fc5808080d40007b2b44bfd938b`, rather than replacing the installed
RC4 with the original feature branch's older RC1 baseline. Linux tab, package
and handoff gates were updated while preserving ROCm/device controls and the
newer narration features.

The installed RC4 also contained four local runtime patches beyond its recorded
commit: `speech_check.py`, `rocm.py`, `native_vulkan.py`, and `rocm_child.py`.
The installed frozen modules were checked against those plain source copies
(the ROCm child executes externally). The same sources were carried forward
byte-for-byte, preserving manual GPU scheduling and the absence of artificial
CPU-thread/RAM/VRAM caps. Cancellation, timeouts, hardware/output validation and
no-silent-fallback checks remain. Source regression: 765 passed, 1 skipped,
17 subtests passed on Python 3.12.14 with the pinned release dependencies.
