# Script Prep 1.0.0 validation — 2026-10-19

- 44 focused tests passed across `test_script_prep.py` and `test_writer_plugin.py`.
  Covers spoken forms, malformed/unsupported numbers, protected addresses/tags,
  dictionary precedence, non-cascading substitutions, durable profiles, corrupt
  file preservation, actual Plugins menu loading, review invalidation, busy-host
  handoff blocking, plugin archive contents and existing writer regression tests.
- Actual source host `ui_smoke_test.run` passed with Script Prep menu lifecycle,
  preparation and review gate, plus the existing host UI checks.
- Inspected a Qt render with the host theme and explicit Segoe UI font loading
  for the sandbox renderer; compact controls and side-by-side scripts fit.
- Built `artifacts/Pronunciation-Script-Prep-Plugin-1.0.0.zip` with SHA-256 file.
  Archive has plugin source, manifest, documentation and MIT license; no models.
- New host builds bundle Script Prep. Existing API 1 hosts can load the external
  plugin ZIP after extraction beside their EXE and restart. A new host EXE or
  installer was not rebuilt as part of this plugin package.
- Text conversion and UI are tested; engine-specific audio pronunciation and
  punctuation timing still need human auditioning. No network/model inference.
- The tested distribution ZIP and checksum are included in `packages/` for the
  repository commit; generated test output and private data are excluded.
