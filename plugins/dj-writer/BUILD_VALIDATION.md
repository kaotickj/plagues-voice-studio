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
