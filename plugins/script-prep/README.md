# Pronunciation & Script Prep 1.0.0

Open **Plugins → Pronunciation & Script Prep**. Load the current Studio script,
open a UTF-8 text file, or paste text. Choose or create a dictionary profile and
enter written terms with spoken spellings. Save dictionaries explicitly.
Prepare a preview, compare the substitutions and line diff, and edit the prepared
text as needed. Review approval is cleared whenever wording or inputs change.
Sending reviewed text uses Studio's normal replacement confirmation and never
starts generation. Copy and export also preserve the original.

Runs offline without a model. Dictionaries are isolated at
`%LOCALAPPDATA%/PlaguesVoiceStudio/plugins/script-prep/dictionaries.json`.
General, Fallout broadcasts and Advertisers start empty: pronunciation hints
are user supplied, not asserted phonetic canon. Each advertiser or DJ can have
a separate profile. Whole words and phrases match case-insensitively, longest
first, once; replacements never cascade. Corrupt files are preserved and saving
is blocked until the file is repaired or moved aside.

Conservative US English rules cover dollar amounts below one million,
percentages, explicit AM/PM clock times, ISO dates and FM/AM/MHz frequencies.
Common titles (Dr., Mr., Mrs.) and vs. can be expanded independently. Optional
dash-to-comma conversion suggests pauses. Other numbers remain unchanged.
Ambiguous slash dates are flagged. URLs, email addresses and existing tags are
preserved for manual review. No SSML, emotion, emphasis or timing tags are
generated: plain spoken text works across Chatterbox, IndexTTS and Qwen3-TTS,
but pronunciation and punctuation timing still require auditioning each voice.
This is a text preparation tool, not audio preview or phoneme synthesis.

Build with `python plugins/script-prep/build_plugin.py`. Extract the ZIP beside
the Studio EXE to create `plugins/script-prep/`, then restart Studio (requires
plugin API 1). New Studio builds bundle it automatically. Python/QWidget plugin,
not a DLL or standalone EXE. Created by Kaotick Jay / Plagued Mods, MIT license.

The tested 1.0.0 installable ZIP and its SHA-256 checksum are also checked in
under `packages/` for download directly from the repository. Generated working
builds remain under the ignored `artifacts/` folder.
