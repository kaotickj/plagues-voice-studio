# Plague's Voice Studio — Linux test build

Experimental **x86-64** portable build, built on Ubuntu 24.04 (glibc 2.39).
Debian 13 is the intended first user test target. Older glibc distributions,
ARM and musl/Alpine are not covered by this build. No Python installation is
needed to run the portable application.

## Debian installer

The **Plague's Voice Studio Linux package** workflow also produces the
`PlaguesVoiceStudio-Linux-amd64-Installer` artifact. It contains a `.deb`
installer and its own `SHA256SUMS.txt`. After downloading and unzipping this
artifact on Debian 13 x86-64, run:

```sh
sha256sum -c SHA256SUMS.txt
sudo apt install ./plagues-voice-studio_*_amd64.deb
plagues-voice-studio
```

APT installs the declared audio and Qt/X11 system dependencies. Launch **Plague's
Voice Studio** from the application menu or use `plagues-voice-studio` in a
terminal. Run the application as your normal user. Its frozen program files live
in `/usr/lib/plagues-voice-studio`; no separate Python installation is required.

The installer contains no AI weights or optional engine environments and does
not download them. It does not configure services or change your existing model
folders. Install/reinstall replaces only the packaged program files. Removal is:

```sh
sudo apt remove plagues-voice-studio
```

Models, recordings, exports and per-user settings remain in their existing
locations after removal. Native optional runtimes still need to be configured;
the installer does not make Chatterbox/Qwen/Index inference hardware-independent.
The `.deb` targets Debian 13 amd64. Other distributions are not established by
this acceptance job; use the portable build where appropriate.

The same workflow builds both formats from one tested onedir tree. A fresh
Debian 13 container installs the `.deb` with dependencies, validates its desktop
entry, exercises the installed runtime and GUI/plugin startup twice, reinstalls
it, then removes it while checking seeded model/settings files are preserved.
Installer and acceptance diagnostics are retained as separate workflow artifacts.

## Run on Debian 13

Install the system audio and Qt/X11 libraries:

```sh
sudo apt update
sudo apt install ffmpeg libsndfile1 libegl1 libgl1 libopengl0 libpulse0 libasound2t64 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 libxcb-randr0 libxcb-render-util0 libxcb-image0
```

Download the `PlaguesVoiceStudio-Linux-x86_64-Portable` artifact from the
successful **Plague's Voice Studio Linux package** Actions run. Unzip that
artifact wrapper, then run these commands inside the download directory:

```sh
sha256sum -c SHA256SUMS.txt
tar -xzf PlaguesVoiceStudio-1.0.0rc1-Linux-x86_64-Portable.tar.gz
cd PlaguesVoiceStudio030Experimental
./start-voice-studio.sh
```

Keep the complete extracted directory together. Extract with `tar` on a Linux
filesystem to retain execute permissions and shared-library symbolic links.
On a Wayland session, try `QT_QPA_PLATFORM=xcb ./start-voice-studio.sh` if the
native Wayland plugin is unavailable; this uses XWayland.

## First test

1. Open Model Manager and install/validate one Chatterbox model (Nano is the
   smallest first test). Models are downloaded on demand, not in the archive.
2. Add a reference recording, generate a short line using **CPU**, play it and
   export its WAV. The bundled PyTorch is CPU-only; selecting CUDA does not
   install a CUDA runtime. Native Vulkan speech experiments are not integrated.
3. Open **Plugins → Promotional Writer** and **Pronunciation & Script Prep**.
   The branded standalone DJ Writer is a separate application.
4. Close/reopen Studio and confirm that saved voices, paths and exports remain.

Shared models/voices use `$XDG_DATA_HOME/PlaguedAI` (normally
`~/.local/share/PlaguedAI`); Studio state is in `apps/voice-studio` under it.
`PLAGUED_AI_HOME` overrides the shared root. Windows Python environments and
llama.cpp EXEs cannot be reused on Linux. Model weights and recordings can be
reused; configure their actual Linux paths instead of copying Windows settings.

## Optional runtimes

Qwen3, IndexTTS and Kokoro use **separate native Linux Python environments**.
Configure their `bin/python` and model/repository paths in Voice Engines, then
use **Test selected engine** before generation. The Windows PowerShell setup
scripts do not install Linux runtimes. Fresh optional-engine setup and real
Linux speech inference remain acceptance work; a passing startup check alone
does not establish them. Kokoro offers CPU on Linux; DirectML is Windows-only.
Writer's verified downloader currently supplies a Linux CPU llama.cpp runtime;
automatic Linux writer Vulkan setup is not included.

Bethesda's Windows FaceFX/xWMA tools are not included or validated through Wine.
Use WAV export while native/Wine conversion acceptance remains outstanding.

## Build from source

On Ubuntu 24.04 x86-64, install the dependencies above plus Git, Python 3.12
with venv support, build-essential and pkg-config, then:

```sh
bash scripts/build_linux.sh
```

The script installs the pinned CPU dependency snapshot into `.venv-linux-build`,
runs the source regression suite, freezes the application, checks runtime/GUI
startup and compares packaged owned modules with source. It then writes a
tarball and SHA-256 manifest to `artifacts/linux/`. CI additionally extracts
the tarball on a fresh runner and repeats runtime and X11 GUI/plugin startup.
No model weights or optional engine environments are bundled.

To build the Debian installer from that already-tested portable onedir:

```sh
.venv-linux-build/bin/python scripts/package_linux_deb.py \
  --app dist/linux/PlaguesVoiceStudio030Experimental \
  --output artifacts/linux-installer
```

The builder uses `dpkg-deb` (the `dpkg` package on Debian/Ubuntu) and does not
require root. It preserves library symlinks, records archive ownership as
root:root and rejects non-amd64 payloads, escaping symlinks, version mismatches
and accidentally bundled model weights. Prerelease versions use Debian's `~`
ordering, for example `1.0.0~rc1-1`, so the final release upgrades correctly.

The GPL v3 binary notice in `BINARY_LICENSE.md` applies to this GUI build too.
Linux uses the system FFmpeg package rather than redistributing imageio's
FFmpeg executable. `BUILD-INFO.json` records the source commit and build host.

Platform packaging references: [PyInstaller Linux compatibility](https://pyinstaller.org/en/stable/usage.html#making-gnu-linux-apps-forward-compatible)
and [symlink preservation](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#requirements-imposed-by-symbolic-links-in-frozen-application).
