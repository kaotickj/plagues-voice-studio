# Plague's Voice Studio release readiness

Updated October 25, 2026. Target: **v1.0.0rc2**, a release candidate for Windows x64 and Linux amd64.

## RC2 evidence and release gates

| Gate | Evidence or required result |
| --- | --- |
| Core narration, preview, profile restoration, reference isolation and export | Source suite: **458 passed, 17 subtests passed, one Windows-only skip** on the qualified local code. Independent Qt checks cover keyboard access, preview text, custom-setting restoration and unsupported-model handling. No extra human-only preview/reference-switch signoff is required by this checklist. |
| Local frozen runtime and package identity | Runtime imports, explicit no-audio GUI diagnostic and **53 owned-source comparisons passed**. Independent archives: **23 portable and 45 DEB checks passed**, including embedded version/commit, executable hashes, permissions and glibc metadata. |
| Local installed upgrade and preservation | Actual Debian RC1/e07 to RC2 upgrade passed. An exact prior DEB and 47 scoped files were backed up; checked user metadata, mappings and five current reference records remained unchanged immediately after installation. Installed runtime and explicit no-audio diagnostics passed. No automatic render was started. |
| Human use | The creator preferred CFG 0.3 over 0.5 in two blind comparisons on one short passage/seed, later reported faster/more concise/more natural generation, and explicitly verified restart persistence. These are bounded subjective reports, not universal improvement or a controlled latency benchmark. |
| Required Windows release jobs | `windows`, `installer_acceptance` and `installer_smoke` must all pass at the final release revision before their binary assets are accepted. Historical RC1 results do not substitute. Publication first prepares a draft. |
| Required Linux release jobs | `build`, `extracted_startup` and `debian_installer` must all pass at the final release revision, including clean install/reinstall/removal and seeded-data preservation. Local archive/upgrade checks do not substitute for those jobs. |
| Required publication | Attach the actual Windows setup EXE and Linux DEB, their portable counterparts, distinct checksum manifests and matching source/build provenance. Verify uploaded names, versions, digests and successful state before publishing the single RC2 draft. Queued CI or source archives alone are insufficient. |
| Model setup | Software tests exercise readiness, cancellation, retry, offline reuse and injected failures. Existing Nano/Turbo tokenizer assets passed offline construction/round trips. These tests do not establish live fresh-download repair or every model's real inference. |
| Desktop audio and optional engines | Headless diagnostics use inert media and do not establish hardware playback. Optional Qwen/Index/Kokoro runtimes and model variants remain separately configured; no all-engine Linux claim follows from Original English tests. |
| Bethesda and other distribution limits | Linux excludes production LIP/XWM/FUZ. Real Windows external-tool/game acceptance, fresh graphical Index onboarding, installer signing and full-offline redistribution remain unverified or outside this RC; they are not claimed complete. |

The local application code was qualified and manually exercised at `ebb921addeb59193565bbf296888a933ab12bdb8`. Subsequent release documentation/trigger changes do not alter application behavior; the final tag's CI artifacts must record their own exact revision. The local Debian build uses glibc 2.41; release CI uses Ubuntu 24.04 and each artifact reports its actual baseline in BUILD-INFO.

**Voice inventory:** the current five-record Debian index is byte-identical to its pre-upgrade backup and all indexed files exist. The historical eleven-reference documentation concerns a Windows profile; six identities were not established locally. No RC2 deletion was demonstrated. Original exemplars may be imported later without deleting existing references; no automatic migration or import is performed.

## Actions cost policy

Run one required Windows release pipeline from the final `v*` tag and one explicitly dispatched Linux release pipeline at that same revision. Ordinary main/documentation pushes do not build the application. Component manual/PR checks remain available; avoid redundant push/tag builds or retries of successful jobs. All required release tests and publication dependencies remain intact. Record actual run URLs/results and assets on the release page and wiki after completion; this file is not a substitute for those results.

## Historical RC1 record

The following October 20 record concerns **v1.0.0rc1** and earlier source. Its checked boxes do not qualify RC2.

## Completed source work

- [x] Generic Promotional Writer bundled through Plugins; branded DJ Writer excluded from the host.
- [x] Canonical AppData storage and legacy-runtime discovery implemented; existing installer identity and upgrade directory retained.
- [x] Corrected update-version parsing and rejection of prereleases in stable update discovery.
- [x] Windows engine cancellation targets the owned process tree. Native cancellation test passed outside the restricted sandbox.
- [x] Python 3.12 CPU dependencies pinned, including Chatterbox and Perth commits; local dependency consistency check passes.
- [x] Source, package, installer and Windows resources agree on 1.0.0rc1; tag checks reject mismatches.
- [x] CI now requires regression tests, frozen runtime/UI checks, isolated installer acceptance and installed-app startup before tag publication.
- [x] Release candidate notes describe limitations.
- [x] Shared PlaguedAI model/voice storage, writer Vulkan integration and Kokoro DirectML adapter implemented and locally rebuilt.
- [x] Python Qwen/Index Windows checkpoint reads and offline Qwen processors repaired; Multilingual tokenizer setup/repair is explicit and verified.
- [x] Windows GUI binary license text, component notices and source directions included; original source MIT license retained.

## Prior user verification

These results precede the new candidate and do not replace candidate acceptance.

- [x] Chatterbox generation and exported transcript workflow worked.
- [x] Qwen3 0.6B generated speech; both Qwen cache checks now succeed.
- [x] IndexTTS 2.5 generated speech after closing other memory-heavy AI applications.
- [x] Generic writer generated useful promotional copy with the saved Gemma model.

## Candidate acceptance gates

- [x] Latest rebuilt portable runtime and GUI/plugin startup pass; host source suite: 287 passed, 1 skipped, including native cancellation.
- [x] Both Python Qwen sizes, IndexTTS 2.5 and Multilingual v3 generated real offline CPU speech from the repaired source with matching script sidecars.
- [x] Real-profile metadata/audio-copy migration passes, all 11 shared voices resolve, repeated startup preserves edits and all 17 original files remain unchanged. No model weights or registry keys copied/modified.
- [x] DJ Writer 0.9.3 installer acceptance passes: verified 0.9.2 payload upgrade, reinstall, repeated startup, uninstall and preservation of five seeded library/settings files.
- [x] Final rebuilt EXE generates real offline speech with Nano, Multilingual v3, both Qwen sizes, IndexTTS 2.5 and Kokoro. Audio validity and exact script metadata checks pass; Kokoro profiling confirms DirectML execution.
- [x] Final payload passes 54 owned-source/package comparisons, portable CRC checks and isolated installer upgrade/reinstall/startup/uninstall acceptance. All 15 seeded data files survive; the prior payload is the verified 0.3.0a4 build.
- [x] Repeat installer acceptance and regression checks after the diagnostic-only Qt settings-isolation fix: clean install/reinstall/repeated startup/uninstall preserve 15 fixtures; 287 existing tests and the new isolation regression pass, 1 skipped. Rebuilt runtime/GUI and 54 source/package comparisons pass.
- [x] Combined revision a543df7 passes Windows build, source/package comparison, isolated reinstall/data preservation and fresh-machine installer startup (run 39526017367). Downloaded checksum/diagnostic artifacts verify success and preservation of 15 fixtures. All three unchanged plugin workflows passed on ed0fd42.
- [x] Published v1.0.0rc1 after tag workflow 39527403701 passed all build/install/preservation gates. Public installer and portable digests match the published SHA-256 manifest. DJ Writer's separate Vulkan update is published as dj-writer-v0.9.3 from successful workflow 39528721997.

## Acceptance retained for general availability

- [ ] Verify intended Bethesda audio/lip-sync workflow in game; automated checks use simulated external tool output.
- [ ] Complete graphical IndexTTS onboarding and a fresh full optional-runtime installation check.
- [ ] Review separately distributed model/full-offline redistribution terms before offering those bundles. Installer signing remains unavailable unless signing infrastructure is supplied.

## Distribution scope

Linux has a separate experimental x86-64 portable workflow targeting Debian 13
with an Ubuntu 24.04 build baseline. See LINUX.md. Its runtime/GUI/extraction
gates and real speech acceptance are independent of the published Windows RC;
the Windows RC's passed checks do not establish Linux readiness.

The standard Windows CPU package excludes model weights and provides model-on-demand setup. IndexTTS uses the documented advanced setup path; complete graphical onboarding remains a general-availability requirement. The full offline edition is separate.

Kokoro presets and writer Vulkan support are in this RC. Experimental native
Vulkan Qwen/Index and ACE-Step tests are outside its supported Studio engine UI.

Only mark measured tests complete. Use the RC for prerelease feedback; do not label v1.0.0 generally available while blocking acceptance or distribution questions remain unresolved.
