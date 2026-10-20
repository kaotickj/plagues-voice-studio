# Promotional Writer 1.1.1

## CPU threading controls

Model setup separates **CPU generation threads** from **Prompt-processing threads**. On Windows, recommended generation threads use detected physical cores; prompt Auto uses logical processors. Existing saved thread choices are preserved. **Use recommended CPU thread counts** applies recommendations explicitly. Higher counts can be slower on memory-bound models; compare the same brief rather than assuming more is faster. This changes throughput, not model intelligence.

Generation remains in a Qt background worker. Interview and writing models run sequentially and unload after each stage. The promotional writer reports model-load time, time from completion request to first text, and the two thread budgets so startup and prompt delays can be distinguished. No parallel copies of the large models are launched.


## Advertiser profiles and two-model workflow

Use **Profile / interview** to create a named advertiser library. Enter its offer, audience, supported facts, voice, call to action and wording/claim boundaries. The guided interview asks for missing core details; **Ask AI follow-up questions** uses the interview model to propose up to three additional questions based on known information. Only your answers become saved facts. Questions and model guesses are not promoted into the library.

Answers can be reusable or campaign-only. Both remain in the local profile for reference; campaign-only answers are added to the current brief and excluded from later reusable context. Saved answers can be reviewed, edited or removed. Unknown/undecided responses are allowed; the interview is instructed not to repeat them as if they were unanswered. Review changing offers, prices, availability and dates before reuse.

**Writing model** and **Interview model** have separate settings. The existing Qwen3 4B file is detected for interviewing when available; Gemma remains the existing/default writing selection. You may change either. The stages run sequentially and each runtime unloads after completing its job. This division of work is supported, not yet a quality benchmark proving a combined model advantage. There is no merged model and no automatic second-model proofreading pass.

Profiles live in `advertisers.json` beside this plugin's settings. Drafting retrieves at most 3,000 characters of the selected advertiser's stable facts and up to four reusable answers; other advertisers and interview history do not enter the prompt. Current brief fields override saved defaults. Missing/conflicting required facts should produce clarification rather than invented claims. A one-off brief remains available without a saved profile.

Generic local copywriting plugin for Plague's Voice Studio. Open **Plugins →
Promotional Writer** in a Voice Studio build with plugin API 1. This is a Python
plugin loaded inside the host, not a renamed EXE or a native DLL. The branded
DJ Writer is separate and is not included in the Voice Studio distribution.

Formats: spoken advertisement, promotional spot, announcement, product
description, social promotion, tagline and custom prompt. Inputs are product,
audience, tone, target length, supplied facts, call to action and custom direction.
There are no inherited DJ personalities, stations or fictional-world prompts.

The model generates drafts and can invent claims despite its instructions.
Review the facts, offer terms and narration wording. Copy and text export work
on editable drafts. **Send to Voice Studio** requires narration approval, asks
before replacing an existing script and never starts speech automatically.
Editing clears approval. Cancelled/failed/incomplete generations restore the
previous draft. Closing during a job cancels it and waits for its owned process.

## Model setup and storage

Model setup can select existing llama-server/GGUF files or download verified,
pinned runtime/model packages. Gemma The Writer 9B is the quality default; Qwen
4B is a smaller fallback. CPU is the baseline. Vulkan remains hardware-dependent.
Model licenses and resource requirements belong to their upstream projects.

On first use, valid runtime/model paths and memory preferences may be read from
the existing DJ Writer setup. No weights are copied; no DJ profile, lore,
continuity, settings or output is imported or modified. The selected local model
is shown in the panel. This does not trigger generation or network access.

Plugin settings and logs live in the stable Voice Studio user-data directory:
`plugins/promotional-writer/` (normally under `%LOCALAPPDATA%/PlaguesVoiceStudio`).
The plugin's own setup is independent after saving. Changing the model path does
not remove downloaded files. Competing main narration/writer jobs are blocked;
close other independent AI programs when memory is limited.

## Packaging and source test

The main Voice Studio spec ships this plugin and its shared `writer_core`
runtime, excluding the themed DJ standalone. Existing frozen Voice Studio EXEs
need rebuilding to gain the Plugins menu; dropping this ZIP into an old build
does not add host support.

Run `python plugins/promotional-writer/build_plugin.py` from the repository to
create the source plugin ZIP and SHA-256 checksum under `artifacts/`. Extract it
beside an API-1 Voice Studio EXE to create its `plugins/promotional-writer/`
folder. Source launches discover the repository's `plugins/` folder directly.

For this checkout, run `plugins/promotional-writer/run_source.ps1` to open the
actual source Voice Studio with the new menu. It prefers an existing local venv;
use `-PythonExecutable` to select another Python with the app dependencies.

## Attribution

Plugin and runtime integration: Kaotick Jay / Plagued Mods. Desktop UI: PyQt6 / Qt.
Local inference: llama.cpp (ggml community). Optional model downloads: Qwen and
Gemma-based community GGUF releases. Their upstream licenses apply. Model
weights and inference binaries are not bundled with the source plugin.
