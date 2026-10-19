# Plague's Voice Studio release readiness

Updated October 19, 2026. Target: **v1.0.0rc1**, a release candidate.

## Completed source work

- [x] Generic Promotional Writer bundled through Plugins; branded DJ Writer excluded from the host.
- [x] Canonical AppData storage and legacy-runtime discovery implemented; existing installer identity and upgrade directory retained.
- [x] Corrected update-version parsing and rejection of prereleases in stable update discovery.
- [x] Windows engine cancellation targets the owned process tree. Native cancellation test passed outside the restricted sandbox.
- [x] Python 3.12 CPU dependencies pinned, including Chatterbox and Perth commits; local dependency consistency check passes.
- [x] Source, package, installer and Windows resources agree on 1.0.0rc1; tag checks reject mismatches.
- [x] CI now requires regression tests, frozen runtime/UI checks, isolated installer acceptance and installed-app startup before tag publication.
- [x] Release candidate notes describe limitations.

## Prior user verification

These results precede the new candidate and do not replace candidate acceptance.

- [x] Chatterbox generation and exported transcript workflow worked.
- [x] Qwen3 0.6B generated speech; both Qwen cache checks now succeed.
- [x] IndexTTS 2.5 generated speech after closing other memory-heavy AI applications.
- [x] Generic writer generated useful promotional copy with the saved Gemma model.

## Candidate acceptance gates

- [ ] Complete frozen runtime and GUI checks on the 1.0.0rc1 payload. Compilation alone is insufficient.
- [ ] Run isolated installer acceptance using the previous 0.3 payload: upgrade, reinstall, repeated startup, uninstall and preservation of seeded user/plugin files.
- [ ] Verify GitHub Actions on the release-preparation commit and inspect uploaded assets/checksums.
- [ ] Test installed candidate generation with Chatterbox, Qwen3 0.6B and IndexTTS 2.5, including reference voices and saved transcripts.
- [ ] Verify actual Qwen3 1.7B inference; cache success alone is insufficient.
- [ ] Verify migration against a backup of real legacy data; synthetic fixtures do not establish this independently.
- [ ] Verify intended Bethesda audio/lip-sync workflow in game.
- [ ] Review redistribution obligations and notices for the app, PyQt6, dependencies and separately distributed models. Sign installer if infrastructure supports it.

## Distribution scope

The standard Windows CPU package excludes model weights and provides model-on-demand setup. IndexTTS uses the documented advanced setup path; complete graphical onboarding remains a general-availability requirement. The full offline edition is separate.

Only mark measured tests complete. Use the RC for prerelease feedback; do not label v1.0.0 generally available while blocking acceptance or distribution questions remain unresolved.
