# Windows binary distribution

The original Plague's Voice Studio and DJ Writer source files retain the MIT
license in LICENSE. The distributed Windows GUI builds include the GPL version
of PyQt6 and are distributed as combined programs under GNU GPL version 3.
The full text is in LICENSES/GPL-3.0.txt. Component-specific notices and licenses
remain applicable; this notice does not change separately distributed model terms.

The corresponding application source, dependency versions and build scripts are
available at https://github.com/kaotickj/plagues-voice-studio . For an official
release use the matching release tag, rather than a later main branch. Build
instructions are in README.md, scripts/build_windows.ps1 and
plugins/dj-writer/build_windows.ps1. requirements-release.txt records the host's
versions and the exact Chatterbox/Perth source revisions. DJ dependencies are
listed in plugins/dj-writer/requirements-build.txt.

Upstream source and distribution information for the pinned GUI dependencies:

- PyQt6 6.11.0: https://pypi.org/project/PyQt6/6.11.0/#files (source distribution).
- Qt 6.11.2: https://download.qt.io/archive/qt/6.11/6.11.2/single/ . Qt DLLs remain
  separate files in the application directory and may be replaced with compatible
  builds. See the Qt distribution's license files and configuration/build tools.
- SIP runtime source: https://pypi.org/project/PyQt6-sip/#files ; use the installed
  version recorded in the package metadata.

The Voice Studio host additionally includes imageio-ffmpeg 0.6.0 (BSD-2-Clause
wrapper) and its unmodified Windows FFmpeg 7.1 essentials executable from Gyan.
That FFmpeg build enables GPL and version 3; it is not an LGPL-only build.
FFmpeg is a separate executable. Upstream release/provenance:
https://github.com/GyanD/codexffmpeg/releases/tag/7.1 . The release identifies
FFmpeg source revision b08d7969c5:
https://github.com/FFmpeg/FFmpeg/tree/b08d7969c5 . Build configuration is available
with the bundled executable's `-version`/`-buildconf` options; the provider's
build and external-library information is at https://www.gyan.dev/ffmpeg/builds/ .
Wrapper source: https://github.com/imageio/imageio-ffmpeg/tree/v0.6.0 .

Additional bundled components retain their upstream licenses. The application
includes THIRD_PARTY_NOTICES.md and dependency metadata/license directories
under _internal. Speech/writing/music weights, optional engine environments,
FaceFXWrapper, Bethesda assets and Vulkan probe runtimes are not included in
the standard slim host installer. Review their separate terms when installing
or distributing them.
