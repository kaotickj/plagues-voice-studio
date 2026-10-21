# Plague's Voice Studio release readiness

Updated October 20, 2026. Target: **v1.0.0rc1**, a release candidate.

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
- [ ] Verify fresh GitHub Actions for the final release-preparation commit and inspect uploaded assets/checksums. On ed0fd42, all three plugin workflows passed; the host build passed packaging but its runner lost communication during installer acceptance. A diagnostic rerun is required.
- [ ] Publish the matching prerelease tag only after the final package and CI gates pass.

## Acceptance retained for general availability

- [ ] Verify intended Bethesda audio/lip-sync workflow in game; automated checks use simulated external tool output.
- [ ] Complete graphical IndexTTS onboarding and a fresh full optional-runtime installation check.
- [ ] Review separately distributed model/full-offline redistribution terms before offering those bundles. Installer signing remains unavailable unless signing infrastructure is supplied.

## Distribution scope

The standard Windows CPU package excludes model weights and provides model-on-demand setup. IndexTTS uses the documented advanced setup path; complete graphical onboarding remains a general-availability requirement. The full offline edition is separate.

Kokoro presets and writer Vulkan support are in this RC. Experimental native
Vulkan Qwen/Index and ACE-Step tests are outside its supported Studio engine UI.

Only mark measured tests complete. Use the RC for prerelease feedback; do not label v1.0.0 generally available while blocking acceptance or distribution questions remain unresolved.
