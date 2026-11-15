# Development sync validation — 2026-11-15

Preserves the existing Linux Bethesda development checkout's Speak As, Seed-VC, direct conversion, warm-worker, audio export and packaging source changes. This is development source, not a release or a merge into main.

Validation used Python 3.12, offscreen Qt, temporary application state and offline model settings. The source baseline passed 903 tests with 3 skips and 17 subtests. The compatible RC4 native-process fixture race fix and its two regression cases are also retained. The final combined tree passed 905 tests with 3 skips and 17 subtests. No real microphone, model inference, installer deployment or live application restart was performed.

## Preserved RC4 alternatives

The separate speak-as-rc4 checkout remains unchanged. Four test files there are not directly portable to this implementation: launcher coverage expects external checkpoint selection and removal of the GPU-lock setting; packaging fixtures omit the newer seed_conversion, fast_asr and speak_as_export modules and use older report keys; smoke tests expect _check_speak_as_dialog and worker_script_path, whereas this implementation uses _check_speak_as and inline worker resolution. These differences require deliberate reconciliation before release. Existing current-source tests pass; that does not establish model-backed audio quality or complete packaging acceptance.

Only curated Python, spec and documentation files are committed. Models, recordings, runtime configuration and build artifacts are excluded. GitHub workflows remain unchanged; this commit uses the documented skip marker.
