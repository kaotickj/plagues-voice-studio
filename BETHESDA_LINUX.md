# Bethesda voice export on Linux

This is the native Linux Studio running Windows conversion tools through Wine.
It is not a native Linux port of Bethesda's tools. Speech synthesis and native
FFmpeg stay on Linux; converting an existing recording does not require a GPU
or hold the speech-generation GPU lock. Native Windows execution remains available.

## What has actually been checked

On November 8, 2026 the actual `export_dialogue` API passed a real-tool Fallout 4
export on Debian 13 using GE-Proton11-11 `files/bin/wine`, a fresh dedicated
prefix, and official CK `LipGenerator.exe`, `FonixData.cdf` and `xwmaencode.exe`.
It created fresh LIP/xWMA, installed a FUZ into an isolated staging mod directory,
round-tripped its contents and decoded non-silent 44.1 kHz mono audio. Paths with
spaces were exercised. No game installation or existing game prefix was changed.
See [BETHESDA_LINUX_VALIDATION.md](BETHESDA_LINUX_VALIDATION.md) for the exact
runtime, measured outputs, negative controls and FaceFXWrapper results, and
[BETHESDA_RELEASE_CHECK.md](BETHESDA_RELEASE_CHECK.md) for regression coverage.
FaceFXWrapper 0.41 also passed the actual export API for Fallout 4, Skyrim and
Skyrim SE after the optional GE vendor-runtime setup below. This is not a
fresh-machine installation, native Windows acceptance or in-game lip-sync
verification.

Successful execution on that Wine build does not establish compatibility with
all distro Wine, Proton, Creation Kit, FaceFXWrapper or codec versions. Each
game still needs in-game checks; Fallout 4 LIP is not interchangeable.

## 1. Install the Linux application and system dependencies

Follow [LINUX.md](LINUX.md) first. The portable application currently targets
x86-64 Debian 13 / a compatible glibc distribution. These commands are
instructions for the user, not an automatic installer. Review apt's proposed
changes before agreeing:

```sh
sudo apt update
sudo apt install wine wine64 ffmpeg libfreetype6
command -v wine wineboot ffmpeg
wine --version
ffmpeg -version
```

Some 32-bit Windows tools, including the x86 FaceFXWrapper, require 32-bit Wine
support unless your Wine build provides a compatible new WoW64 configuration.
For Debian's multiarch Wine packaging, inspect the package candidates and then
install the matching 32-bit runtime if needed:

```sh
dpkg --print-architecture
dpkg --print-foreign-architectures
sudo dpkg --add-architecture i386
sudo apt update
apt-cache policy wine wine64 wine32:i386
sudo apt install wine32:i386
```

Use packages from your configured Debian repositories with matching versions.
Do not mix random Wine DLL downloads or unrelated Wine repositories. If apt
cannot find candidates, check your distribution's supported Wine instructions
rather than force-installing packages from another release. See
[Debian Wine guidance](https://wiki.debian.org/Wine).
Wine and FFmpeg are not installed by the Studio diagnostics button.

## 2. Create a dedicated prefix with the selected runner

A Wine prefix is a directory containing its Windows-like registry and drive
layout. Use a new prefix for these tools, not a running game's prefix, Steam's
`compatdata` prefix, or your ordinary `~/.wine` environment. Do not run Wine as root.
For system Wine:

```sh
mkdir -p "$HOME/.local/share/pvs-bethesda"
WINEPREFIX="$HOME/.local/share/pvs-bethesda/wine-prefix" wineboot -u
WINEPREFIX="$HOME/.local/share/pvs-bethesda/wine-prefix" wine winepath.exe -w "$HOME"
```

Wait for initialization to finish. Enter that exact absolute prefix directory
in Studio. Studio requires an existing initialized prefix and does not run a separate
initialization command. Wine itself can update a selected prefix when invoked,
so keep the same runner for initialization and export.
Do not point a different Wine version at a valuable existing prefix to experiment.
Wine may show optional component installation prompts; review them yourself.

### Using an already installed Proton Wine instead

Select the actual executable inside your installed compatibility tool, such as
`.../GE-Proton11-11-x86_64/files/bin/wine`. Do not select the `proton` Python
launcher, a Steam application ID or a Windows `wine.exe`. Studio invokes Wine
itself and does not implement the Proton launcher environment or Steam runtime.
Direct execution only works for builds whose bundled Wine can run this way.
For a compatible installed build, adapt both paths below:

```sh
WINE_BIN="$HOME/.steam/root/compatibilitytools.d/GE-Proton11-11-x86_64/files/bin/wine"
PVS_PREFIX="$HOME/.local/share/pvs-bethesda/ge-wine-prefix"
"$WINE_BIN" --version
WINEPREFIX="$PVS_PREFIX" "$WINE_BIN" wineboot.exe -u
WINEPREFIX="$PVS_PREFIX" "$WINE_BIN" winepath.exe -w "$HOME"
```

Select `WINE_BIN` and `PVS_PREFIX` in Studio. Do not literally type `$HOME` or
shell variable names into a file picker: choose the resolved paths. This guide
does not install Proton or recommend replacing a functioning Wine setup.

### Optional GE-Proton11-11 FaceFXWrapper runtime completion

Direct `files/bin/wine` does not run Proton's usual prefix preparation. In the
specific GE-Proton11-11 trial, FaceFXWrapper initially could not map its embedded
CK payload because Wine's graphics DLL import chain could not find three VKD3D
DLLs. Copying the six architecture-specific files already supplied in that same
installed GE build's `default_pfx` into a **new dedicated test prefix** resolved
the observed loader failure. No DLL override or extra environment variable was
needed. The official Fallout 4 LipGenerator route did not require this step.

Use this only if your selected GE installation actually has those files. This is
not a general Wine fix, a GPU requirement for voice export, permission to fetch
random DLLs, or an instruction to change your game's prefix. Do not mix DLLs
from another Proton release. After initializing the new prefix in step 2, set
`WINE_BIN` and `PVS_PREFIX` to that runner and prefix, then run:

```sh
export WINE_BIN PVS_PREFIX
python3 - <<'PYTHON'
import os
from pathlib import Path
from shutil import copyfileobj

wine = Path(os.environ['WINE_BIN']).resolve()
prefix = Path(os.environ['PVS_PREFIX']).resolve()
assert wine.name == 'wine' and wine.parent.name == 'bin'
assert (prefix / 'system.reg').is_file(), 'Initialize the dedicated prefix first'
source = wine.parent.parent / 'share/default_pfx/drive_c/windows'
pairs = []
for arch in ('system32', 'syswow64'):
    for name in ('libvkd3d-1.dll', 'libvkd3d-shader-1.dll', 'libvkd3d-utils-1.dll'):
        src = source / arch / name
        dst = prefix / 'drive_c/windows' / arch / name
        assert src.is_file(), f'No vendor file: {src}; stop, do not substitute'
        assert dst.parent.is_dir(), f'Missing prefix directory: {dst.parent}'
        assert not dst.exists() and not dst.is_symlink(), f'Already present: {dst}; inspect first'
        pairs.append((src, dst))
for src, dst in pairs:
    with src.open('rb') as incoming, dst.open('xb') as outgoing:
        copyfileobj(incoming, outgoing)
    print(dst)
PYTHON
```

This copies only the same vendor's three DLLs into each matching architecture
folder and refuses to replace existing files. Studio does not perform these
copies automatically. Keep runtime setup inside this private prefix; do not add
these files to Studio, your mod or a redistributed tool bundle. See the
[validation report](BETHESDA_LINUX_VALIDATION.md) for precisely which exports
passed after this step; in-game animation remains unverified.

## 3. Acquire the game tools from their proper sources

Keep conversion tools outside the Studio application directory so application
updates do not replace them. Keep the original runtime/support files with the
tools. The app uses native Linux paths and maps tool arguments using the selected
Wine's `winepath.exe` and prefix; do not manually change every path to `Z:`.

### Fallout 4: official Creation Kit backend

Install Fallout 4 Creation Kit through its official distribution and review its
terms. Locate `LipGenerator.exe`, `FonixData.cdf` and `xwmaencode.exe` in your
installation; use versions belonging to that installation. The data is commonly
under `Data/Sound/Voice/Processing`, and audio tools under `Tools/Audio`.
A read-only search of a chosen installation can help:

```sh
find "/absolute/path/to/Fallout 4" -type f \( -iname 'LipGenerator.exe' -o -iname 'FonixData.cdf' -o -iname 'xwmaencode.exe' \)
```

The official LipGenerator backend is Fallout 4 only. It is not a substitute
for Skyrim's generator and is distinct from CK's plugin-level `-GenerateLips`
workflow. The application generates a line from audio and transcript, not a
plugin's dialogue records. Supply the Fonix file separately in the setup fields.

### Skyrim / Skyrim SE, or optional Fallout 4: FaceFXWrapper

Use [Nukem9's official FaceFXWrapper releases](https://github.com/Nukem9/FaceFXWrapper/releases).
The inspected upstream release is [0.41](https://github.com/Nukem9/FaceFXWrapper/releases/tag/0.41)
(December 8, 2021). Download `FaceFXWrapper.0.41.zip` from that release's Assets,
not an unrelated similarly named wrapper. Its archive contains
`Tools\Audio\FaceFXWrapper.exe` and `README.txt`; it does not contain Fonix data.
Retain the included README with your local installation. Its game-directory
`Tools/Audio` layout describes integration with the Creation Kit; Studio uses
standalone command-line mode instead. Source inspection of 0.41 confirms that
CLI mode loads CK code embedded in the wrapper, not a CK executable found by
walking up from its directory. Studio can keep the wrapper outside the game
and use a scratch working directory with explicit paths. Obtain `FonixData.cdf`
from your own authorized CK/GECK installation.
Review [upstream usage and licensing](https://github.com/Nukem9/FaceFXWrapper#license).

Studio supplies already-resampled 16 kHz, mono, 16-bit PCM input using the
six-argument form, with `Skyrim` for Skyrim/SE and `Fallout4` for Fallout 4.
The language currently used by this integration is `USEnglish`; validate using
English dialogue. Selecting a game is necessary even when the tools are shared.

**Licensing is split:** the wrapper's own code has an
[MIT license](https://github.com/Nukem9/FaceFXWrapper/blob/master/LICENSE.md), but
upstream explicitly identifies CK code and compressed resources governed by
Bethesda's agreement. An MIT repository badge is not permission to redistribute
the entire compiled EXE or Fonix data. No such permission was established in
this review. Keep these user-supplied, outside public installers and source trees.
The archive's own README also warns that LIP correctness has not been validated.

### xWMA encoder choices

- **Creation Kit xwmaencode:** choose the executable from your authorized CK
  installation. This is the encoder used in the successful Wine experiment.
- **WMAEncodeRS:** optional [upstream project](https://github.com/MSIVST/WMAEncodeRS),
  whose [source license is MIT](https://github.com/MSIVST/WMAEncodeRS/blob/main/LICENSE).
  It uses Windows Media Format codecs (`wmvcore.dll`). Wine having a DLL with
  that name does not prove the encoder works. Its Linux/Wine runtime is not
  established by the official-tool test. Preserve the MIT notices if distributing
  its code/binary, separately review dependencies, and do not assume permission
  to redistribute Microsoft's codecs. This build does not bundle WMAEncodeRS.

FFmpeg prepares the PCM input; the configured encoder must produce real RIFF/xWMA.
Renaming MP3, WMA/ASF or PCM WAV to `.xwm` cannot replace the xWMA stage.

## 4. Configure Bethesda Voice Export

Fresh Linux settings select official Fallout 4 LipGenerator and CK xwmaencode.
Existing saved FaceFXWrapper paths retain that backend, and explicit saved
choices remain respected. Check your selections rather than relying on defaults.

1. Choose **Game** and the exact owning plugin filename. For the first trial,
   use a staging mod directory and an existing known CK dialogue response.
2. Under **Lip generator**, select **Official CK LipGenerator (Fallout 4 only)**
   or **FaceFXWrapper (user supplied)** as appropriate.
3. Set **Windows tool runner** to **Wine / Proton Wine executable**. Browse to
   the real Linux Wine executable and the dedicated initialized **Wine prefix**.
4. Browse to the **Lip generator executable**, **FonixData.cdf**, and **xWMA
   encoder executable**. Match the **Encoder** selection to that executable:
   **Creation Kit xwmaencode** and **WMAEncodeRS** take different arguments.
5. Set **Native FFmpeg executable** to `/usr/bin/ffmpeg` if automatic discovery
   does not find the distro package. FFmpeg is not run through Wine.
6. Click **Check tools and save settings**. These checks inspect paths and
   configuration; they do not execute tools, install dependencies or prove codec
   compatibility. No audio or saved project is required just to inspect setup.
7. Select an existing recording and check its transcript against the actual
   spoken words. Choose VoiceType and the exact CK response filename. A voice
   recording alone cannot identify the plugin record or destination basename.
8. Confirm the destination preview. An existing game Data folder gets
   `Sound/Voice/<Plugin>/<VoiceType>/<Response>.fuz`; an MO2 mod root has the same
   relative layout, without adding another `Data` directory.
9. Keep source outputs for the first test and export. Allow time for Wine startup;
   increase **Tool timeout** only if a legitimate run needs longer. Cancellation
   and timeouts are failures, not successful exports. Fresh outputs are required
   even when a Windows utility misleadingly returns exit code zero on error.
10. Play the exact dialogue in game and verify sound, mouth animation, duration
    and alignment. Test Fallout 4, Skyrim and Skyrim SE separately before
    claiming support verified. Back up existing dialogue files before replacement.

## Troubleshooting

- **Missing prefix / winepath:** complete step 2 with the same executable. Check
  that `system.reg`, the drive layout and executable permissions exist. The app
  does not fix prefix architecture or upgrade it automatically.
- **Bad EXE / missing DLL / architecture error:** confirm actual PE tool files,
  matching bitness support and original adjacent dependencies. Do not download
  individual DLLs from random sites or change system security settings.
- **FaceFXWrapper: “Failed to map CK executable into memory”:** the named CK
  image is embedded inside the wrapper, not a missing installed `CreationKit.exe`.
  In the tested GE-Proton11-11 environment, its Wine import chain was missing
  bundled VKD3D DLLs; the optional vendor-runtime procedure above resolved this
  and all three game-profile exports passed. That fix is specific to the tested
  layout. For another runtime, inspect loader diagnostics instead of moving the
  wrapper into the game, copying CK executables or fetching random DLLs.
- **Unexpected CK IPC behavior:** standalone invocation must not inherit a
  nonempty `Ckpid` variable from a Creation Kit session. Upstream uses that
  variable to choose IPC mode rather than process the supplied CLI arguments.
- **No LIP despite exit code zero:** check the backend/game pairing, correct
  Fonix data, matching transcript, tool logs and paths. This happened with a
  deliberately missing WAV in the preliminary official-tool experiment.
- **Fonts warning:** install the distribution's FreeType runtime appropriate to
  your Wine build. The preliminary GE test emitted a FreeType warning while
  still producing validated containers; do not generalize that every warning
  is harmless.
- **xWMA fails:** confirm encoder selection and codecs. WMAEncodeRS's MIT license
  does not provide its Windows Media runtime. Try your already installed official
  CK encoder rather than treating a plain WAV as xWMA.
- **Access denied / paths:** choose readable inputs and a writable staging mod
  root. Do not run Studio as root. Spaces are supported; Wine drive mappings must
  make both inputs and export working paths reachable.
- **Valid FUZ but wrong/no animation:** confirm game profile, exact response name,
  VoiceType, deployment and actual in-game acceptance. Container validation is
  not a decoder or proof of correct facial animation.

Report distribution, Studio revision, Wine version/path, prefix type, selected
game/backend/encoder, tool version and stage error. Do not attach proprietary
EXEs, Fonix data, account details or whole Wine prefixes to public bug reports.
