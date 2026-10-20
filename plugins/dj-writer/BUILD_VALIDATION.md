# DJ Writer 0.9.2 installer and portable - October 19, 2026

The Windows packaging workflow now builds a per-user Inno Setup installer and
a versioned portable ZIP, with separate Actions artifacts and shared SHA-256
checksums. Local build passed 148 regression tests, frozen startup/icon smoke
and installer compilation. Portable CRC, license and README inclusion checks
passed. Outputs: artifacts/DJ-Writer-Setup-0.9.2.exe and
artifacts/DJ-Writer-0.9.2-Windows-Portable.zip. User data remains in the existing
home-directory location; no installer delete rules target it. Actual installer
install/upgrade/uninstall acceptance has not been run for DJ Writer. Models
are not bundled. Generated binaries remain local/Actions artifacts.

# DJ Writer 0.9.2 CPU threading - October 19, 2026

Shared runtime now supports separate generation and prompt-processing thread counts, Windows core-aware recommendations and backward-compatible settings. Local recommendation: 6 generation / 12 prompt threads. Existing user counts are preserved. 148 tests and the rebuilt frozen 0.9.2 startup/icon check pass. ZIP: plugins/dj-writer/artifacts/DJ-Writer-Plugin-Windows.zip. No controlled speed or quality gain is claimed yet. No changes committed or pushed.

# DJ Writer 0.9.1 starter corpus and character memory - October 19, 2026

Executed the 181-topic wiki catalogue builder, then narrative-section enrichment and editorial curation. The final pack contains 143 references: 60 locations, 52 people, 7 factions and 24 creature/daily-life entries. Nineteen topic matches were unresolved at the scope/identity stage, and nineteen further entries lacked useful narrative detail. See lore_curation_report.json for exclusions and attribution in each record. Selected key entries were rewritten as source-grounded editorial summaries rather than appearance lists.

Live Piper Wright and Dogmeat lookups now produce useful Fallout 4-specific references and canonical CC BY-SA 4.0 links. Runtime lookup uses narrative extraction; series index pages are rejected. Writing retrieval is limited to 3 relevant topics, 3 facts per topic, 3,200 characters maximum (lower for short copy); source/license metadata stays in the viewer. Four accepted character notes, up to 1,000 characters, are supplied only for the selected DJ. Generated traits remain review candidates with script provenance.

148 regression tests pass. The 0.9.1 standalone rebuild and frozen startup/icon smoke test pass. Frozen starter JSON matches the curated source; portable ZIP CRC/inclusion checks pass. Live generated-story quality remains subject to user review. No new commit or push has been made.

# DJ Writer 0.9.0 lore reference validation - October 19, 2026

- 139 regression tests pass, including cached/offline retrieval, source/revision retention, redirect alias reuse, missing-page search, response bounds, reference prompt integration and the library settings dialog.
- Live Independent Fallout Wiki lookups for Goodneighbor and The Third Rail succeeded. Revision IDs and source license metadata were retained. Evidence: artifacts/dj-lore-live/.
- Standalone rebuilt to plugins/dj-writer/dist-lore/Goodneighbor Plague Radio DJ Writer/. Frozen icon/startup smoke test passes; portable ZIP and SHA256SUMS.txt are in plugins/dj-writer/artifacts/.
- No speech models, writing models or wiki cache are bundled. Generic Promotional Writer is unchanged. This is retrieval, not fine-tuning; factual correctness of generated stories still needs editorial review.
- Real generated-story quality has not been benchmarked for this change. New source/build remains local pending user testing.

# Local Windows build validation — October 18, 2026

## v0.8.12 three-row layout

- Broadcast controls at top, script/editor/output actions in center, grouped AI
  writing and narration controls below. Bottom settings scroll vertically when
  the window is short; the header is smaller.
- Added a 1000×720 expanded-settings geometry regression for editor/review
  separation, visible output actions and no horizontal settings overflow.
- Rendered normal, compact and expanded-narration layouts.

## v0.8.11 advertiser dropdown

- All 131 regression tests passed, including advertiser availability across all
  formats, the 17 built-in entries, enabled custom campaigns and typed names.
- Visually checked the actual advertiser popup and restored arrow buttons.
- Dropdown SVG is included in the PyInstaller data manifest.
- Build output is isolated under `dist/v0.8.11`. No commit or push.

## v0.8.10 menu repair

- All 130 tests passed, including real menu-triggered dialogs and file export.
- Visually checked actual Help popup, Help dialog and AI Setup dialog with the
  explicit Fusion palette. Removed transparent group-child editor backgrounds.
- Frozen application/icon smoke check passed for v0.8.10.
- Rebuilt under `dist/v0.8.10`; nothing committed or pushed.

## v0.8.9 GUI rebuild

- All 128 regression tests passed in the build environment.
- Rendered the desktop and compact layouts, expanded narration controls and
  About dialog; corrected horizontal clipping in the controls pane.
- PyInstaller portable build and frozen Qt/icon smoke check succeeded.
- Portable archive integrity check passed (152 files).
- The build uses `dist/v0.8.9` so an older running copy is not overwritten.
- Help/About attribution and plugin architecture notes are included. Native DLL
  loading and the Voice Studio Plugins menu remain future work.
- No commit or push was made; this build awaits user testing.

## Earlier validation

- Imported DJ Writer v0.8.5 source from the existing downloaded package.
- Embedded the approved logo as the EXE icon and Qt application/window icon.
- Updated to v0.8.7: removed copyable plot examples, required causal events and a
  concrete payoff, made musical handoffs optional, and added bounded motif
  guidance/review checks. Stories now plan their incident before writing prose.
- All 121 regression tests passed on Windows with Python 3.12.10, including
  all-DJ recipe delivery, other-format isolation, history boundaries, stable
  preview guidance, and valid/invalid internal-plan behavior.
- PyInstaller 6.22.3 produced the portable application successfully.
- Frozen GUI check passed: `{"ok": true, "version": "0.8.7", "icon": true}`.
  It creates a temporary profile, loads the window and bundled content, checks
  both Qt icons, and exits without starting a writing model.
- Build PATH is isolated so unrelated developer-tool DLLs cannot be collected.
- Portable ZIP and SHA-256 checksums are under `artifacts/` (excluded from Git).

Prompt tests check the instructions sent to the model, not generated story
quality. Real Qwen 4B CPU samples were tested in an isolated profile using the
existing installed weights. The final sample finished in 188.7 seconds, but
still contradicted item ownership, introduced an ordinary working bus, and
ended abstractly. It also missed the requested length (259 vs 350 words).
The prose-quality problem is NOT considered solved by the passing tests.
Raw test drafts and diagnostics are retained under ignored `artifacts/`.

Gemma The Writer 9B comparison: one Tal story completed in 380.26 seconds on CPU
with four threads, 213 words against a 250-word target, with no automatic review
warnings. It maintained a reported-source frame and a causal action/consequence
sequence, but invented questionable bureaucracy involving a canon character and
repeated its concluding point. This is a qualitative single-sample comparison,
not proof of reliable lore accuracy or a matched-length performance benchmark.
The final planner additionally receives the shared Commonwealth constraints and
is told not to invent offices/policies for canon characters; that last wording
change was regression-tested but not separately evaluated with another real render.
The user's saved model selection was not changed. Quality was prioritized over
speed; Gemma is recommended for the next editorial test, not declared validated.

Pending user testing: visible icon/taskbar appearance, existing profile/model
reuse, real AI generation, speech directions and reviewed script export.
The new Actions workflow has not run remotely. Nothing has been committed or
pushed as part of this plugin packaging work.
