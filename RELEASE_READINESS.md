# Plague's Voice Studio — v1.0 release-readiness checklist

Updated October 17, 2026. **Source changes in open pull requests are not completed release validation.** Check the actual GitHub Actions build and test a newly installed Windows binary before ticking the release gates.

## Confirmed on the creator's Windows machine
- [x] Chatterbox speech generation works, including exported script preview/copy.
- [x] Qwen3-TTS Base 0.6B generates speech and saves its original text to JSON.
- [x] IndexTTS 2.5 generates speech and saves its original text to JSON when other resource-heavy AI software is closed.
- [x] The four Chatterbox models are available through Model Manager with download/validation.
- [x] Help/About document the supported local engines.

## Work implemented, awaiting merge and real Windows validation
- [ ] **Automatic CI:** PR #7 enables Windows builds for merges to `main`; the current default-branch workflow still builds pushes to `develop`/tags only. Merge and verify a real automatic run.
- [ ] **Small installer:** PR #7 adds `-Slim` and excludes bundled Chatterbox weights. Confirm the setup EXE and portable ZIP are under the GitHub Releases per-file limit, install cleanly, and fetch models through Model Manager.
- [ ] **Permanent AppData:** PR #9 normalizes writable storage to `%LOCALAPPDATA%\PlaguesVoiceStudio`, safely copies portable v0.3 data and retains legacy models/runtimes. Test against a backup of real user data, confirm unchanged old folder and successful second launch.
- [ ] **Final transcript regression gates:** PR #6 adds extra package/UI tests. Verify the installer contains the exact JSON-saving source and that both WAV and MP3 previews work.
- [ ] **Update discovery:** PR #8 adds nonblocking, opt-in update checks linking to official releases. Test offline behavior, release version comparisons, and upgrade workflow.

## Open release blockers
- [ ] **Qwen3 1.7B:** Download/validation currently fails on creator's Windows machine. Capture the specific model-download log; confirm cache integrity, free disk space, and actual inference. Do not advertise 1.7B as ready until verified.
- [ ] **IndexTTS onboarding:** Provide a documented, graphical install path for ordinary Windows users, with license acknowledgement, dependency checks, hardware/CPU fallback, download progress, recovery and clear error messages. The existing PowerShell setup remains an advanced fallback.
- [ ] **Installer upgrade:** Test clean install, reinstall/upgrade over existing v0.3, migration, old voices and engine settings, portable build, and uninstall behavior, while preserving older data.
- [ ] **GitHub Release publishing:** After PR #7, test stable vs prerelease tags, successful Windows install smoke test, official GitHub asset upload, portable/checksum files, and update checker against a real published release.
- [ ] **Distribution compliance:** Review application and each bundled upstream dependency/model license, PyQt6 distribution obligations, notices, watermarking and redistribution permissions. Sign the final installer if distribution infrastructure supports it.
- [ ] **Release freeze:** Pass Windows regression tests and a real render in each supported engine with a newly installed distribution; resolve reproducible crash/data-loss issues; pin dependencies and publish v1.0.0 notes.

## Release policy
The full offline Chatterbox edition is a separately hosted distribution option if it exceeds GitHub Releases' 2 GiB per-file asset limit. The standard v1.0 installer should be small, contain no model weights, and use Model Manager for user-approved Chatterbox downloads. Preserve separate Qwen3 and IndexTTS dependencies without silently changing working installations.

**Do not call v1.0.0 generally available while an open release-blocking test remains unresolved.** A tagged prerelease can be used for external feedback. Mark tasks complete based on measured Windows output, not the presence of source code alone.
