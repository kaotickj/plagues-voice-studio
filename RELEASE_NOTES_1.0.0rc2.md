# Plague's Voice Studio 1.0.0rc2

This release candidate is being qualified locally. No RC2 publication or replacement of an installed application is implied by these notes.

- **Natural Narration (Original English)** is an opt-in profile for built-in and reference voices. It uses CFG 0.3, temperature 0.8, expressiveness/reference conditioning 0.5, 220-character segments and 180 ms segment gaps. Current settings remains the default; switching back restores custom controls. Two voices favored CFG 0.3 in blind listening on one short passage and seed. This is limited naturalness evidence, not a universal quality improvement.
- The profile is visibly unavailable for Nano, Turbo and Multilingual V3. Qwen3-TTS and IndexTTS retain their separate workflows. Plain narration receives no added vocal effects. Original manuscripts, prepared render input and effective settings stay separate in export metadata.
- Nano/Turbo readiness now includes tokenizer assets. A directory with weights but missing tokenizer files remains eligible for download/repair instead of being reported installed. This checks file completeness, not model integrity or successful inference.
- Linux DEB dependency metadata follows the recorded build's glibc baseline. The local Debian 13 candidate does not establish Ubuntu compatibility. Linux excludes the Windows-only Bethesda production workflow.

The installed app, shared models, references, recordings and permanent settings identities are preserved by this work. Windows installer identity and legacy executable/directory names remain stable for upgrade compatibility. RC2 has its own version so it can be distinguished from RC1.

Source tests, frozen runtime checks, real speech/listening, clean install/upgrade, desktop playback and Windows/Bethesda acceptance are separate gates. See [release readiness](RELEASE_READINESS.md) for current scope and remaining work. Do not treat historical RC1 results as RC2 evidence.
