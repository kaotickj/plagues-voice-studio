# Plague’s Voice Studio — Assistive speech

Run `plagues-assistive-voice` from an installed source environment, or run `PYTHONPATH=src python -m chatterbox_studio.assistive` from the checkout using a Python environment with Studio's Qt dependencies. The locally installed companion also has a **Plague’s Assistive Voice** application-menu entry.

Requires Linux with `pw-loopback`, `pw-dump`, and `pw-play`. Configure the existing local Kokoro runtime/model directory in Engine Lab for quick preset speech. Saved-voice synthesis and recording conversion reuse [Speak As configuration](SPEAK_AS.md). This source entry point does not install system audio services or download engines. The frozen Studio package does not yet expose this separate companion entry point.

1. Choose **Type a phrase** or **Record a phrase**.
2. Typed speech defaults to a quick local CPU preset. Choose **Saved voice — IndexTTS** to use the existing voice library instead. Saved voices and recording conversion retain the explicit CPU/GPU selector and existing cooperative GPU lock.
3. For recording, click **Start recording**, then **Finish recording** (20-second maximum). The system's default microphone is used; capture requires 16 kHz mono PCM. Losing window focus cancels capture. Direct Seed-VC/Chatterbox conversion changes the voice but may retain speech difficulties. The IndexTTS recording method transcribes locally and pauses for you to correct the words; **Prepare speech** then uses your selected quick or saved voice.
4. Preview if desired. **Enable virtual microphone**, then choose **Plague’s Voice Microphone** as input in the receiving application. Click **Send to microphone**. Enabling the device alone sends no phrase. Speakers are used only by Preview.
5. **Stop / cancel** stops owned recording, processing and playback. Disable the microphone or close the window to remove the temporary device. No defaults, system audio files or security settings are changed.

Ctrl+Enter prepares typed/corrected text. Escape stops. Phrases are temporary and replaced by the next preparation; Save WAV preserves a result. No phrase history is retained. Saved WAV exports follow the existing Studio export behavior. No external service or model download is used.

## Scope and limits

This is a separate companion based on Studio source commit `49e0cf9d74e662a85f087e41014969306ba58fed`, with the existing engines, voice library and settings read in place. It does not replace the installed Studio or modify its settings. It depends on the existing Studio Qt runtime, configured local engines, and PipeWire tools.

Phrase-based conversion is implemented; continuous real-time conversion is not. Earlier installed Seed-VC evidence measured 143.36 seconds cold and 30.53 seconds warm for an approximately 11.6-second output. These historical figures are not a fresh benchmark of the companion. Fresh GPU timing was deferred to preserve active work.

The real UI was verified with CPU synthesis, synthetic recorded speech through local transcription, explicit sending, and a separate `pw-record` receiver. The initial implementation's channel-map syntax was corrected before release; final routing checks verify no automatic links, unchanged default devices, successful receipt and cleanup. Physical microphone usability, listening quality, speech-impediment recognition, and Zoom/Discord/browser-call acceptance remain untested. Applications must allow selecting a system audio input; no universal compatibility claim.

Closing the companion removes its session-owned virtual microphone. Removing a separately installed companion launcher does not require changing the main Studio application, voices, or settings.
