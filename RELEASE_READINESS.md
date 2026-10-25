# Plague's Voice Studio release readiness

Updated October 25, 2026. Target: **v1.0.0rc2**, a release candidate undergoing local qualification.

## RC2 qualification checkpoint

| Gate | Current evidence and limit |
| --- | --- |
| Narration profile, preview, settings and export software tests | Focused source checks pass, including independent Qt tests with isolated settings and media stand-ins. They do not test desktop playback or real model audio. |
| Quality evidence | On the prior qualified Linux build, the creator preferred CFG 0.3 over 0.5 for both Original English built-in and one approved reference voice, using one short passage and seed. Exact audio was saved for listening. This supports the optional profile, not a universal default change. |
| Final RC2 source and frozen artifacts | Must pass the full source suite, dependency/version consistency, frozen imports, source identity and GUI startup after all final changes. Prior `aac92f9` packages do not include RC2 changes. |
| Linux packaging | Portable/DEB inspections passed on prior `aac92f9`. RC2 needs its own package and install/upgrade/removal/data-preservation evidence. The local build host is Debian 13/glibc 2.41; Ubuntu 24.04 compatibility is unqualified. |
| Model setup | Source-level discovery/cancellation/retry/offline tests use synthetic files or injected failures. Live fresh downloads and every model's real inference are not established by those tests. The Nano/Turbo tokenizer-readiness repair needs the final regression suite. |
| Desktop audio | Current local GUI tests use the explicit no-audio diagnostic; sound-server access is unavailable in the execution sandbox. No bypass is permitted. Human listening of delivered files is separate from app playback. |
| Windows package/install | Current RC2 build and clean installer acceptance are unrun. An authorized major-test Actions run must bind the final source commit; routine pushes/builds are not authorized. |
| Bethesda | Production LIP/XWM/FUZ workflow is Windows-only and excluded from Linux. Real external-tool and in-game acceptance remain unrun for RC2; simulated-tool tests do not establish them. |

Before installation or publication, report the final candidate, exact source/artifact identities, measured tests and remaining platform limitations. A Linux-only prerelease must be explicitly scoped; it cannot inherit Windows readiness. No Actions run, tag publication, model download or installed-app replacement is authorized by this checklist.

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
