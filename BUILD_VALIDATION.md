# Speech release-blocker repair - October 20, 2026

Both Qwen sizes, IndexTTS 2.5 and Multilingual v3 completed offline Python CPU
generation with the Windows reader/local-tokenizer repairs. Outputs are finite,
non-silent WAVs with matching script sidecars. 287 host tests pass, 1 skipped,
including native cancellation. Installed Index dependency consistency is clean.
See SPEECH_LOADING_VALIDATION.md and artifacts/release-speech-repair/.

The refreshed DJ 0.9.3 installer/portable passes 148 regression tests and frozen
startup/icon checks. Isolated acceptance upgraded the verified 0.9.2 payload,
reinstalled, repeated startup and uninstalled while retaining all five seeded
library/settings files. Final report: artifacts/dj-installer-acceptance/
b0246ffbeca44e3b82e26a2c67d9b6a7/result.json. Earlier failed/staging attempts
remain separate. The new packages include binary license/source notices.

Real-profile migration acceptance uses isolated metadata/audio copies: legacy
voices resolve after migration, all 11 consolidated voices resolve through the
shared library, repeated startup preserves edits, and all 17 original source
files retain their hashes. No model weights or registry keys are changed.
Evidence: artifacts/release-speech-repair/real-profile-migration/
66915c742b714acc8b5364d661fb7821/result.json.

Fresh host packaged inference and installer acceptance are recorded separately
as they complete; source success does not replace those gates.

# All-model Radeon retest - October 20, 2026

Five writing/text models, Gemma vision, both Qwen speech sizes, IndexTTS 2.5,
all six Kokoro presets, both ACE-Step music variants and their shared components
completed actual Radeon inference. BART, MPNet and MiniLM also passed isolated
DirectML inference. Native Chatterbox port failures and additional Python
baseline failures remain explicit. Fourteen successful WAV outputs passed
finite/nonempty/non-silent checks. Full matrix, limitations, provenance and
reproduction: GPU_MODEL_AUDIT.md; private evidence: artifacts/gpu-model-audit/.
Native speech/music probes have not been wired into Studio menus. No application
production code changed after the final Kokoro package validation below.

# Kokoro Radeon speech integration - October 20, 2026

Added six preset voices to Voice Engines with speed, character profiles, WAV
metadata, diagnostics and export handoff. Kokoro uses a separate ONNX Runtime
environment; existing reference-voice engines retain their settings. Default
Auto prefers DirectML when installed, with explicit DirectML/CPU choices.

All six voices generated real speech on CPU and again on RX 7600 XT DirectML.
The GPU path uses a cached equivalent padding graph, preserving the original
INT8 model and learned tensors. Twelve independent operator parity cases pass
with zero numerical difference. Profiling confirms thousands of DirectML GPU
events per sample; unsupported operations use CPU. See KOKORO_VALIDATION.md.

Regression suite: 269 passed, 1 skipped, 1 deselected (existing native process-tree
cancellation test). Source and frozen GUI/runtime smoke checks pass. The actual
rebuilt executable also passes --kokoro-self-test, generating speech through its
isolated external interpreter with 4,363 DirectML events. Relevant PYZ modules
and bundled runner match source, and portable ZIP CRC/checksum pass.

Ready local test package: artifacts/kokoro-host/PlaguesVoiceStudio-Kokoro-Portable.zip.
Evidence: artifacts/kokoro-host/, artifacts/kokoro-gpu-validation/ and
artifacts/kokoro-graph-parity/. No new Studio installer, commit, push or public
release has been produced. The broader all-model Radeon audit is separate.

# Shared AI storage and Radeon writer builds - October 19, 2026

Completed local consolidation under %LOCALAPPDATA%/PlaguedAI: 11 voices, eight
storage trees and verified compatibility junctions. Twelve byte-identical model
copies were replaced with hard links. Imported and SHA-256 verified all 26
distinct server files representing nine models plus the Kokoro voice pack.
See SHARED_AI_STORAGE.md; private inventories and model files are not committed.

Real Gemma Writer 9B and Qwen3 Instruct 4B generation passes on the RX 7600 XT
using the pinned b11703 Vulkan runtime. Excluding the Mirillis capture layer
only in Windows Vulkan child processes resolves the native loading crash.
Matched CPU/GPU trials, actual generated text and timings are documented in
VULKAN_VALIDATION.md. Writing and interview preferences now use the verified
shared GPU runtime, with original settings backed up. Speech backends are
unchanged; ACE-Step and Kokoro weights are copied but not integrated into Studio.

Host regression suite: 258 passed, 1 skipped, 1 deselected (the existing native
process-tree cancellation test). DJ Writer: 148 passed. The final frozen host
passes runtime and GUI/plugin smoke checks; DJ Writer 0.9.3 passes its frozen
startup/icon check and its installer compiles. Both PYZ archives were compared
against current project source, including the GPU workaround and migration
helper; all included modules match. Both portable ZIPs and both plugin ZIPs
pass CRC checks. Evidence: artifacts/shared-storage-package-validation.json,
artifacts/shared-storage-host/, and artifacts/shared-storage-*-gpu-build.log.

Local test outputs: artifacts/shared-storage-host/PlaguesVoiceStudio-SharedStorage-Portable.zip;
plugins/dj-writer/artifacts/DJ-Writer-Setup-0.9.3.exe and
DJ-Writer-0.9.3-Windows-Portable.zip; Promotional Writer plugin 1.1.2.
No new Voice Studio installer, tag or public release was produced. DJ installer
install/upgrade/uninstall acceptance and speech generation after migration still
need acceptance. These changes and generated packages have not been committed
or pushed. The records below describe earlier validation stages.

# Plugin delivery validation - October 19, 2026

Prepared the pending writer/lore/threading changes together with Pronunciation &
Script Prep 1.0.0 for repository delivery. The installable Script Prep ZIP and
SHA-256 are tracked in plugins/script-prep/packages/. Host regression suite:
247 passed, 1 skipped, 1 deselected (the existing native process-tree cancellation
test). DJ Writer regression suite: 148 passed, plus 99 subtests. Script Prep and
writer targeted suite: 44 passed. The actual source host GUI smoke test passed.
Local models, generated evaluation data, large build artifacts and the unrelated
user image are excluded. The records below describe earlier validation stages.

# Real library-data generation comparison - October 19, 2026

Generated eight real Gemma 9B CPU drafts (four promotional ads, four DJ stories including actual planning) using fixed seed 731, 6/12 threads and 8,192-token context. Compared original no-library mode, an instruction-matched empty-library control, focused references and cluttered references. Used synthetic advertiser facts, offline source-linked lore and a constant DJ character note. No user business/character files were modified.

Focused advertiser facts improved specificity but did not eliminate overclaims; the empty control still invented expertise and parts-quality claims. DJ references supplied canonical names without reliably fixing causal logic: errors already appeared in generated plans. Extra facts did not yield a clear quality win and added latency in this sample. One seed and one brief per writer do not establish a general ranking; Qwen and the independent effect of character memory remain untested.

All eight drafts completed successfully. Unedited text, prompts/payloads, story plans, timings, fixtures, review and output SHA-256 hashes are under artifacts/library-ablation/ (REPORT.md). Reproduction scripts: scripts/evaluate_writer_libraries.py, scripts/evaluate_writer_empty_controls.py and scripts/report_writer_libraries.py. No production code was changed during this evaluation.

# Writer profiles/threading portable preview - October 19, 2026

Built a separate complete CPU slim host under dist/WriterProfilesPreview with Promotional Writer 1.1.1 (advertiser interview/profile libraries, separate interview/writing model settings, shared CPU thread controls). Frozen runtime and GUI/plugin checks pass. The packaged Python files match current source and portable ZIP CRC passes. Archive and SHA-256: artifacts/writer-profiles-host/. Host suite: 223 passed, 1 skipped, 1 deselected (unchanged restricted native process-cancellation test); 21 targeted plugin tests pass. No new main installer or public release was produced. Preview changes remain local and uncommitted.

# Completed local installer acceptance - October 19, 2026

After the user authorized retrying, the isolated acceptance test passed. It installed the previous 0.3 payload, upgraded to 1.0.0rc1, reinstalled, verified runtime and GUI startup at every stage, then uninstalled. All nine synthetic user-data/plugin sentinels retained their SHA-256 hashes. The test used a separate AppId, no shortcuts and a workspace-only target; it did not install over the user's real application. Evidence: artifacts/installer-acceptance/09030ea1b2b7455cad71987077b30889/result.json and adjacent reports/logs. This supersedes the earlier permission-review-blocked GUI/installer status below. Real legacy-profile migration and installed-engine inference still need user acceptance.

# CI bootstrap repair - October 19, 2026

Run 39204861363 failed during dependency metadata preparation: Perth requires uv_build, absent from the no-build-isolation bootstrap. Added pinned uv_build 0.12.7 before installing the dependency lock and put the venv Scripts directory on PATH so its executable can be found. A fresh workspace Python 3.12 venv successfully built the exact pinned Perth commit with these tools (artifacts/ci-perth-wheel.log). Ten targeted release/packaging tests pass. Updated checkout/setup-python to Node 24 action versions. A new hosted build must still confirm the full pipeline.

# Release candidate 1.0.0rc1 validation - October 19, 2026

Built locally using Python 3.12.10 and the pinned Windows CPU toolchain.

- Source suite: 216 passed, 1 skipped, 1 deselected. The deselected Windows process-tree cancellation test passed separately with normal Windows permissions (1 passed). Restricted sandbox process termination prevents that test from running reliably there.
- Dependency consistency and release/tag identity checks pass.
- Frozen runtime self-test passes, with project metadata 1.0.0rc1 and PyTorch 2.6.0+cpu. Initial sandbox launch timed out; the approved launch outside the sandbox passed.
- Frozen GUI self-test and isolated installer acceptance have not executed: automatic permission review failed at capacity (installer review also timed out before its permitted retry). These remain release gates; no successful installation is claimed.
- Inno Setup compiled the single-file production installer successfully: 289,421,943 bytes.
- Portable ZIP: 406,503,543 bytes; CRC integrity passes. Generic writer is included; branded DJ Writer and model weights are excluded.
- Packages, runtime report and SHA256SUMS.txt: artifacts/1.0.0rc1/. Logs: artifacts/rc1-*.log. Generated artifacts are not committed.
- GitHub Actions and installed-engine generation on this candidate remain unverified. No release tag or public release has been created.

The following sections are historical records, superseded by this candidate's results where they differ.

# Windows writer-plugin portable rebuild — October 18, 2026

The complete CPU slim portable host was rebuilt in a separate
`dist/WriterPluginPreview/PlaguesVoiceStudio030Experimental/` directory. The
actual frozen EXE passes runtime and GUI self-tests, including the new Plugins
menu and generic Promotional Writer close/reopen checks. The branded DJ
standalone and speech/writer model weights are excluded. No installer was made.

36 targeted speech, narration-markup and plugin tests pass in the complete
build environment. The broader suite retains 15 confirmed baseline failures;
one additional Windows temporary-log cleanup failure passed on isolated rerun.
See `plugins/promotional-writer/BUILD_VALIDATION.md` for details. Portable ZIP,
checksums and frozen reports are under `artifacts/writer-host-build/`.

Nothing committed or pushed; the portable build awaits user testing.

# Earlier experimental 0.3.0-alpha1 validation

Source environment: Linux authoring container, October 16, 2026.

- Frozen **stable v0.2.4 source** preserved independently as an identical ZIP; SHA-256 `23464fb7c541e000d03f2c47f14e18629fe70d97f1b9b4d4ebadf556776d5928`.
- Python syntax: `python -m compileall -q src scripts tests launcher.py optional_engine_runner.py`, verified.
- Python tests: `pytest -q`, including pure-Python JSON IPC mock-runner tests. 65 passed, including 9 optional-engine regression tests.
- ZIP integrity and checksum: performed after building the release archive.
- **PyQt6 is not available in this authoring container.** The experimental Qt app was not rendered on Windows here.
- **Qwen3-TTS and IndexTTS weights and runtimes were not installed or invoked with real voice inference here.** The subprocess protocol and output handling were tested against a simulated isolated interpreter.
- Windows build script will reject a missing or failing frozen-runtime/GUI report, as in earlier versions. The GUI smoke test checks About, Help and the new Engine Lab before permitting archive/installer packaging.
- AMD acceleration, real inference timbre, model performance and in-game Bethesda export are not verified.

## Isolation review

- Experimental source/metadata, application settings, Windows executable, installer identity and per-user data root are separate from v0.2.4.
- Previous v0.2.x and v0.1.x voices are read-only; no hidden migration or writes to stable user data.
- Qwen/Index optional Python packages are not installed or bundled in the Chatterbox environment.
- Child runner processes have explicit executable paths, JSON request/response files, no shell string or HTTP listener, and cancellation/timeout support.
- Character profiles and generation sidecars are saved in experimental paths only.

## Limitations

No native Windows EXE has been generated here. Upstream TTS APIs, especially IndexTTS's CPU support, may require a local compatibility patch as APIs change. This release is a development alpha, **not a production replacement**.
