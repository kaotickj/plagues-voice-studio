# Promotional Writer validation — October 18, 2026

## Complete Windows host rebuild

- Built the full CPU speech-enabled slim portable host under
  `dist/WriterPluginPreview/PlaguesVoiceStudio030Experimental/` using the separate
  root `.venv-build` (Python 3.12.10, CPU PyTorch/torchaudio 2.6.0, Chatterbox 0.1.7).
  Existing portable applications were not overwritten.
- Source speech-runtime imports and 36 targeted speech/markup/plugin tests pass.
- The actual frozen EXE passes both `--self-test` and `--ui-self-test`, including
  the real Plugins menu and generic writer close/reopen lifecycle.
- Portable ZIP and SHA-256 manifest are in `artifacts/writer-host-build/`.
  Full archive integrity and generic-plugin inclusion were checked. The themed
  DJ standalone and speech/writer model downloads are excluded from the host.
- Rebuild command: `./scripts/rebuild_writer_host.ps1` after installing the host
  build dependencies. The exact installed dependency snapshot is recorded in
  ignored `artifacts/writer-host-dependency-lock.txt`.
- Full suite in this complete environment: 183 passed, one skipped, 15 confirmed
  baseline failures plus one Windows probe-log cleanup failure. The cleanup test
  passed its isolated rerun. The unrelated baseline issues remain unchanged.

- 13 plugin-specific tests pass: prompt isolation, facts/CTA inputs, runtime-only
  settings import, manifest/API/path validation, single-instance menu lifecycle,
  idle close/reopen and busy cancellation, reviewed handoff, overwrite refusal,
  streamed completion/truncation, model alias startup, prior-draft restoration,
  host model-operation guards and package contents.
- 50 affected plugin/optional-engine/storage/packaging/GUI tests pass.
- All 132 DJ Writer regression tests pass after extracting the shared runtime
  and setup UI; DJ-specific story and radio prompting remains separate.
- The actual source Voice Studio UI smoke test passes with its real Plugins menu:
  open generic writer, close, reopen the same instance and close again. No model
  download, speech generation or automatic writer job occurs on panel creation.
- Inspected actual host-loaded panel screenshots at 1100×850 and 900×680.
  Editor, source fields and output actions fit. Dropdown arrows and disabled
  narration-handoff styling are explicit.
- A real Gemma The Writer 9B Q4_K_M CPU run completed in 34.14 seconds and produced
  a 54-word repair-shop advertisement using the supplied business, free-estimate
  offer, address, opening days and phone. No DJ or fictional-world framing.
  This is one sample, not a guarantee of model quality or factual correctness.
- Source plugin ZIP and SHA-256 manifest are generated under `artifacts/`.
  Archive contents exclude DJ standalone code/assets, EXEs and model weights.

The broader host suite had 20 unrelated failures: five speech tests require
PyTorch, which is absent from this lightweight validation environment; twelve
update-version tests and three old UI-string assertions also fail on an isolated
copy of committed HEAD. Baseline recheck: 15 failures reproduced, four tests
passed. Those unrelated files/expectations were not repaired by this feature.

The main PyInstaller spec includes only the generic plugin plus shared core,
and its frozen UI smoke check exercises the plugin menu. The full portable EXE
has now been rebuilt and validated as above; a new installer has not been made.
Existing old EXEs do not gain a menu from the small plugin ZIP alone. Launch the
rebuilt portable EXE for testing. Windows workflows have not been pushed or run
remotely.

Nothing committed or pushed; user testing remains the release gate.
