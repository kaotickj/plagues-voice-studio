# Goodneighbor / Plague Radio DJ Writer v0.9.4

## Prepared spots and reusable offer terms

Choose **Website Promo** for goodneighborblues.com. The quick-template selector
offers a plain invitation, percentage-off offer, fixed-price deal, subscription
introductory deal and a single-feature promotion. **Edit terms** collects exact
amounts, items, billing periods, introductory duration, renewal terms and optional
codes/deadlines/eligibility. Terms are saved under the DJ data folder in
`spot_template_terms.json`; verify current terms each time you reuse them.
Missing required terms stop generation before a model is loaded.

Every spot type has a prepared project-specific default. Simple IDs, openers,
breaks, song links and closers have shorter suggested lengths. **Prepared copy**
uses the selected template directly, without loading a writing model; the
optional AI brief applies only to **Write with AI**. Song links use the supplied
title/artist controls. Original Commonwealth stories still need an original
draft rather than a stock story.

Website/offer prompts use the Goodneighbor Blues website identity, exclude
Fallout lore and character-memory lookups, and avoid inventing subscriber perks
or terms. Ordinary station formats preserve the selected host's home station;
Mister The Plague's Plague Radio identity remains available.

## Radeon Vulkan and shared AI storage

Writing and interview models can use the shared llama.cpp Vulkan runtime and
existing models under `%LOCALAPPDATA%\PlaguedAI`. Select the Vulkan compute
backend in Model setup with a compatible GPU runtime. CPU remains available.
The Windows runtime excludes the conflicting Mirillis capture layer only in
its own Vulkan subprocesses; it does not change system capture settings.

On the tested RX 7600 XT, Gemma Writer 9B and Qwen3 Instruct 4B completed real
Vulkan generation. See [measured results](https://github.com/kaotickj/plagues-voice-studio/blob/main/VULKAN_VALIDATION.md). Hardware,
model loading and context size affect speed. Vulkan improves execution speed;
the models retain their existing writing abilities and do not train themselves
from requests. Review generated drafts and accept character notes explicitly.

Windows installer and portable packages include checksums and binary license
notices. Model weights and inference runtimes are installed separately and
can be reused by Promotional Writer. The DJ standalone remains separate from
Voice Studio's generic Promotional Writer plugin.

## CPU threading controls

Model setup separates **CPU generation threads** from **Prompt-processing threads**. On Windows, recommended generation threads use detected physical cores; prompt Auto uses logical processors. Existing saved thread choices are preserved. **Use recommended CPU thread counts** applies recommendations explicitly. Higher counts can be slower on memory-bound models; compare the same brief rather than assuming more is faster. This changes throughput, not model intelligence.

Generation remains in a Qt background worker. Interview and writing models run sequentially and unload after each stage. The promotional writer reports model-load time, time from completion request to first text, and the two thread budgets so startup and prompt delays can be distinguished. No parallel copies of the large models are launched.


## v0.9.1: Curated starter pack and character notes

The standalone now bundles 143 source-linked Fallout 4 narrative references built from a 181-topic catalogue. Weak introductions, index/disambiguation pages and uncertain topic matches are excluded. The curation scripts fetch descriptive article sections, select useful roles, relationships, motives and setting details, and hold insufficient entries for review. `lore_curation_report.json` records exclusions. Source credits and CC BY-SA license metadata remain with each entry; they are not included in the model context.

Generation retrieves at most three relevant topics with three facts each, capped at 3,200 characters and reduced further for shorter scripts. Accepted character notes are limited to four per host and 1,000 characters. The full library is never sent to Gemma. Reference material does not make a host omniscient or establish player/quest outcomes.

**Lore library → DJ character notes** keeps a separate journal for each host. Generated habits/preferences/backstory become candidates with script fingerprints. Accept or reject them, or add editor-established notes. Only accepted notes enter future planning/drafting. Existing profiles and editor continuity take priority. Quoted dialogue is excluded from automatic collection; extraction is conservative and may miss details.

To rebuild and curate the starter corpus from the wiki (run in this folder):

```powershell
python build_lore_library.py --output lore_starter.json --report curation-fetch-report.json
python enrich_lore_library.py --pack lore_starter.json --report curation-enrichment-report.json
```

The second stage selects narrative material and excludes entries without useful detail. Review the resulting pack and reports before distribution. Original editorial adaptations for key characters live in `lore_enrichment.py`. Runtime lookups use the same narrative extraction, reject index pages such as generic Dogmeat, and resolve a Fallout 4-specific article where possible. Bundled references work offline; downloaded updates remain in the user library. Removing a bundled entry hides it locally without changing the installed starter pack.

## v0.9.0: Commonwealth reference library

AI Studio now has a **Lore library** button. Ten original factual starter notes cover the main Commonwealth settings and common lore mistakes. Automatic wiki lookup is enabled by default and can be disabled in this dialog. Before drafting, up to three relevant topic names are looked up on the Independent Fallout Wiki. Full briefs, profiles, scripts and continuity are never sent to the wiki. Lookup may expose quest spoilers.

Successful lookups save a bounded article introduction, source URL, revision ID/time, attribution and license metadata under `<DJ data folder>/ai_writer/lore_library/`. Saved wiki references are reused for 30 days, then refreshed when relevant; up to 200 articles are retained. Offline or failed lookup falls back to curated and cached notes. Search/refresh individual topics in the dialog, inspect their sources, or remove a saved article. This is reference retrieval, not model training or a guarantee of canon accuracy. Cross-game and conditional quest information must still be reviewed. Generated drafts never become library facts automatically.

Relevant references reach story planning and drafting as labeled data. Editor continuity remains separate. View prompt uses the current local library without making network requests; a subsequent automatic lookup can add references before generation. The generic Promotional Writer remains free of Fallout lore and lookup.

## v0.8.12: Three grouped control rows

Broadcast selections sit across the top. The center holds generation, history,
the script editor, review, copy and export. Writing setup/brief and narration
tools share the bottom row. Horizontal dividers resize the rows; the bottom
settings area scrolls vertically on short windows. A minimum-size regression
check protects the editor and export controls from overlap and horizontal overflow.

## v0.8.11: Advertiser dropdown

Restored visible dropdown buttons throughout the GUI. The advertiser selector
keeps all 17 built-in names and enabled custom campaigns, accepts custom typed
names, and remains selectable across formats. Only relevant prompts consume
the advertiser selection. Custom campaign data is preserved.

## v0.8.10: Menu and dialog repair

Use a consistent Fusion palette for Windows popups, editor viewports and dialogs,
with explicit menu/list colors. File actions now reflect script availability
and review approval. Tools actions are unavailable during generation. Regression
checks trigger every Tools, Help and About action through its real Qt signal,
open and close its dialog, and verify the reviewed export path.

## v0.8.9: Script desk and help

The forest-green desktop now has a logo masthead, resizable side-by-side writing
controls and script editor, collapsible narration tools, and a compact reviewed
export card. Help covers setup, editorial review, narration and model memory;
About includes creator attribution and third-party credits. Editing a script
still resets review approval. Short-link cleanup also removes unsupported quoted
song credits and time claims from model-generated links.

The standalone application remains branded. The proposed shared-core, generic
Voice Studio plugin interface is documented in `../PLUGIN_ARCHITECTURE.md`;
the host plugin loader and a native DLL are not implemented in this release.

## v0.8.8: All radio prompts rewritten

All nine format prompts, shared delivery rules, station descriptions, DJ voice
instructions and factory profile/lore text have been rewritten. Tal is measured
and articulate, Hattie practical and sharply wry, and Plague sardonic and
theatrically suspicious. Standard spelling is the default for every host;
texture belongs to speech performance rather than an invented written drawl.
Existing custom profiles, saved models and continuity are preserved.

Each format has one broadcast job. An opener welcomes and identifies; an ID
identifies; a break provides one brief observation; song links use only supplied
metadata; an ad uses supplied business facts; a closer signs off without starting
a new story. Random mix makes one short item, not a broadcast sequence. Stories
retain source/action/payoff planning with a more compact recipe. Commonwealth
details constrain the writing rather than being compulsory decorations.

Short-format defaults are now 90 words for openers, 25 for IDs, 50 for breaks,
40/35 for song intros/outros, 90 for ads, 60 for closers and 50 for random mix.
Stories remain 600 words. All targets remain editable; format purpose takes
priority over padding. The readable current catalog is `PROMPT_DEFAULTS.md`.
Openers, IDs and closers additionally receive a short sentence-order contract.
Gemma uses more restrained sampling for these formats and song links; story
sampling remains unchanged. This reduces improvisation but does not guarantee
that a model follows every instruction.
Gemma then copy-edits those five short formats to remove unsupported time/show
claims, emotional promises and stock slogans. Only the edited result is saved
as a completed script; a failed edit restores the previous result. This adds a
model call in the same owned runtime. Story planning, other formats and Qwen's
sampling behavior are unchanged by this short-link editing step.

## v0.8.7: Grounded anecdotes and story variety

Removed the copyable example openings and plots. The recipe now requires a
clear chain of actions and consequences and a concrete payoff. Witnessed facts
stay distinct from a source's claims; unexplained mysticism cannot replace an
incident. A musical handoff is optional and must not invent tracks or playlists.

Each request gets a broad source/payoff direction without a canned plot. An
explicit source in the brief takes priority. Up to six recent drafts supply at
most eight fixed motif labels to guide variety, never raw text, names, facts or
instructions. The model is told to vary the combination; brief-requested elements
remain allowed. Review notes flag some recycled motif combinations and openings
that omit the host's connection to the incident. These are editorial aids, not
automatic judgments of coherence or story quality.

Stories now use two model calls in the same local runtime: a short internal JSON
plan (source, goal, obstacle, action, outcome, closing aside and the specific
Commonwealth condition driving the incident), then the spoken
draft. Only the draft streams into the editor. A malformed or truncated plan
fails the request without saving a completed script. Cancellation and runtime
cleanup apply to both stages. This adds planning time; other formats keep their
single writing call. Plans are draft fiction and never become saved continuity.
The prompt viewer shows the drafting guidance; the plan is created at runtime.
Story prose is directed toward literal conversational observations and a short
closing reaction rather than a philosophical paragraph. Some recurring cryptic
closing phrases are flagged for review; these checks cannot judge all endings.

**Story-quality testing:** the existing Qwen 4B preset still produced continuity
and logic errors in local tests despite stronger instructions. Gemma The Writer
9B gave a more coherent source/action/consequence sequence in one comparison,
but still needed lore and ending edits. For quality-focused story testing,
select Gemma in AI Setup; the update does not silently change saved selections.
Both models remain draft generators, and the larger CPU run is substantially
slower. See `BUILD_VALIDATION.md` for measured results and limitations.

## v0.8.6: Stories told on the radio

Stories From the Commonwealth now follows a five-beat radio anecdote recipe:
hook and source, concrete scene, a Fallout-specific incident, the DJ's response
and source reliability, then a payoff and a short return to the ongoing broadcast.
The selected DJ tells something they personally witnessed or attributes it to a
traveler, trader or other source. Reported claims stay distinct from firsthand
knowledge. The output is spoken radio copy, without story titles, recipe labels,
omniscient narration or an end-of-broadcast sign-off. The third-person literary
story direction has been replaced in both the default prompt and final request.
Existing profiles, writing models and other formats remain compatible.

## Voice Studio companion plugin package

This source now lives in `plugins/dj-writer` in the Voice Studio repository.
It includes the approved DJ Writer logo as both a multi-resolution Windows EXE
icon and the Qt application/window icon. The application still runs separately;
its writing behavior, model locations and existing user profile are retained.

Run `build_windows.ps1` (or double-click `build_windows.bat`) on Windows with
Python 3.12. The build runs the tests, creates an onedir EXE, checks the packaged
GUI/icon with a temporary profile, and writes a portable ZIP plus checksum in
`artifacts/`. Build output is in `dist/Goodneighbor Plague Radio DJ Writer/`.
Always keep its EXE beside the entire `_internal` folder.

The repository's `DJ Writer plugin Windows package` workflow builds the same
package; it does not publish a GitHub Release. See `../README.md` for scope.

**AI Studio writes new radio scripts with a local language model.** Each request
produces one complete, editable draft: a station break, commercial, musical segue
or episode of **Stories From the Commonwealth**. The original Classic Generator
and Ad Manager are retained.

Created for Plagued Mods / Goodneighbor Records. Writing and speech remain
separate applications. This update does not modify a Voice Studio installation.

## Speech-ready scripts, improved in v0.8.5

**New:** AI Studio now shows a live, throttled speech-direction preview while a
story is streaming, and refreshes the finished script automatically. Raw chunks
stay in an independent internal buffer so generated tags never become the
writing model's input. The 350 ms preview is approximate; very short or fast
scripts may appear only at completion.

For *Stories From the Commonwealth*, the director can respond to a quietly
painful family story with a restrained `[whispering]` transition after the
`[narration]` opening (Balanced/Expressive), without adding coughing or crying
sounds to the storyteller just because a child is ill in the script. Original
words, punctuation and paragraph breaks are preserved. The `Subtle` setting
avoids inferred whispers. `IndexTTS 2.5` and `Qwen3-TTS (official)` instead get
untagged text and separate per-sentence emotion guidance.


**Speech-ready output is ON by default, with Chatterbox Turbo preselected.** The
editor displays automatically tagged output upon generation completion, not only
a preview. Nano uses the same native tag vocabulary. Direction is applied after
the separate local writing model writes the spoken text, so the draft's creative
content and DJ personality remain unchanged. For example, commercial scene
setting can be `[narration]`, the first sales pitch `[advertisement]`, and a dry
punchline `[sarcastic]`, without repeating `[advertisement]` every sentence.

Use **Apply cues to script** after editing or switching engines. The 19 exact
Turbo/Nano native tags are available in an **Insert tag at cursor** picker. The
IndexTTS and Qwen3 options preserve clean spoken text and export their own JSON
emotion/delivery data, requiring a separate consumer in Voice Studio. See
`SPEECH_DIRECTION.md` for the full list, examples and backend limitations.

## Run

Use Python 3.10 or newer:

```bash
python -m pip install -r requirements.txt
python goodneighbor_dj.py
```

Windows users can launch `run_windows.bat` after installing requirements.
`build_windows.bat` builds a separate Windows EXE using PyInstaller. Distribute
the whole resulting `dist/Goodneighbor Plague Radio DJ Writer` folder. This
archive contains source, not a precompiled Windows executable or model weights.

## First AI setup

1. Open **AI Setup**. Keep **CPU** selected for the baseline configuration.
2. The CPU starting model is **Qwen3 4B Instruct 2507, Q4_K_M**, a 2.50 GB
   community GGUF. **Gemma The Writer, Mighty Sword 9B, Q4_K_M**, 5.64 GB, is an
   optional story-oriented candidate. Both are separate from Qwen3-TTS.
3. Click **Install writing runtime** to get the pinned official llama.cpp build
   (about 20 MB on Windows), then **Download / resume model**. Downloading happens
   only when requested. Interrupted model downloads can resume; final files must
   match their pinned size and SHA-256 before use.
4. For large 9B models, leave **Disable weight repacking (--no-repack)** checked.
   This avoids potentially multi-gigabyte CPU_REPACK allocations during startup.
   Enabling repacking can improve CPU throughput on machines with plenty of
   allocatable memory, but the additional allocation may fail on Windows.
5. Click **Save setup**. Future writing uses the downloaded local files offline.

You can **Browse** to an existing writing GGUF and llama-server executable instead
of downloading again. Keep the runtime's DLLs/libraries next to the executable.
For another compatible GGUF, choose **Other compatible GGUF**, its chat template
must be present, and set its native context size. Other models need independent
validation. The two supplied presets are non-thinking writing configurations.

**Voice Studio's installed Qwen3-TTS Base 0.6B/1.7B is a speech model.** It turns
supplied text into audio; it is not the Qwen instruction model used for writing.
Those speech weights cannot be reused as the script-writing model. Keep using
them to perform approved scripts in Voice Studio.

The optional Windows **Vulkan** runtime is intended for compatible AMD and other
GPUs. Select Vulkan, install that runtime, and save setup. CPU inference remains
available. The Vulkan preset explicitly selects `Vulkan0`, the first Vulkan
device; check that the diagnostic log identifies your intended GPU. RX 7600 XT acceleration, memory use and speed require an on-machine
test; no CUDA dependency is introduced. The included Linux installer supplies
CPU x64 binaries. Other platforms can select their own compatible runtime.

## Built-in Fallout writing prompts

Every format now has its own predefined prompt. **The extra-direction box is
optional.** Select a DJ and type, then Write with AI to use the defaults. Your
own brief adds a premise, product detail or story beat to that guidance.

- **Stories From the Commonwealth:** one original, complete episode with a
  concrete opening, character stakes, a complication and a resolution. The
  default is 600 words. Tal, Hattie and Plague have distinct story directions.
- **Ad / promo:** one spoken commercial using the advertiser's known business,
  campaign details and exact supplied slogan, with an in-world call to action.
  All bundled advertisers have background facts. An empty advertiser becomes
  a home-station promo; an unknown business name does not invent its trade.
- **Openers, closers, IDs and breaks:** distinct radio formats, each carrying the
  correct host, home station and musical character.
- **Song introductions/outros:** use supplied titles and artists without
  inventing biographies, trivia or lyrics. Blank metadata produces a generic
  musical segue. Random mix selects one short format.

Goodneighbor Blues **95.77** keeps Tal and Hattie’s warm, reflective, wry blues
identity. Hattie retains her Mama Mire persona. Plague Radio keeps Mister The
Plague’s pirate-metal identity, suspicious humor and unreliable theories.
No numerical frequency is established for Plague Radio. Cross-promos describe
the advertised station while preserving the host's home identity.

Lore guidance keeps the action in Fallout 4's Commonwealth. Project-created
stations, businesses and incidents stay fan fiction. Rumors are not established
facts, and unprovided player choices, faction victories and quest outcomes stay
open. Scripts avoid modern online advertising and borrowed dialogue or lyrics.
These are writing instructions, not an automatic canon-verification system.

**View writing prompt** shows the actual assembled guidance, including your
editable profile, lore, continuity and optional brief. This view works before
installing a model. Changing the DJ or format updates the default and preserves
anything you typed in the extra-direction box. Clear that box to return to a
request using only the defaults.

The defaults live in `script_prompts.py`; **PROMPT_DEFAULTS.md** is the readable
catalog. They also apply to existing v0.7.0 profiles without replacing custom
personality notes, campaigns, history or model paths. No model re-download is
needed for this update.

## Write one script

1. Select **AI Studio**, the DJ, format and mood.
2. Set **Target words** and optionally describe an idea in the brief. The target is
   approximate. Stories default to 600 words and can request up to 2,000.
3. For a commercial, select an advertiser. Custom **Ad Manager** descriptions
   and slogans are included in the writing prompt. One request writes one spot.
4. Click **Write with AI**. Text streams into the single editor. The model runs
   in its own process and unloads after that request to release memory.
5. Edit the draft. Check the host's voice, setting details, continuity and ending.
   Mark **I have reviewed this script for narration**, then export or copy it.

**Cancel** stops only the current writing process, discards the unfinished draft
and restores the previous script. Failed requests also restore the previous
script. Neither creates a completed history entry. A cancelled/failed request
never falls back to curated text while claiming it was AI written.

Drag the divider above the script buttons to give long drafts more editor room.
The settings panel scrolls on smaller screens.

**Previous result** shows one completed historical script at a time. Generation
does not add output numbering. There is no quantity, variants or bulk-generation
control. Multiple paragraphs belong to the same script.

## Characters, lore and continuing stories

**Profiles / continuity** contains an editable character profile and episode
notes for each host, plus shared setting/lore. Tal and Hattie keep their warm,
reflective blues identity. Mister The Plague has his own suspicious, sardonic,
metal-radio identity.

Maintain observed facts, rumors, disproven theories and unresolved threads in
the notes yourself. Model inventions never become saved continuity automatically.
Shared lore can hold details that Tal and Hattie must both remember. Recent
drafts are checked for repetition after generation. Stories also use fixed motif
labels for variety before generation; raw drafts are never fed back as lore.
Only the editor-maintained notes supply continuing facts.

The editor flags likely truncation, excessive length differences, placeholders,
wrong-station references, missing station IDs, missing advertiser names or
changed slogans, and strong repetition. Ads also flag unsupported numeric
prices, clock times and some named locations. These
are review aids. They do not establish Fallout canon, detect every contradiction
or guarantee the requested prose quality. Every new draft starts unapproved;
editing clears approval. No script enters narration automatically.

Gemma The Writer's native context is 8,192 tokens. That budget includes the
profile, lore, continuity, brief and generated script. AI Studio tokenizes the
request before inference and reports an actionable error if it leaves too little
writing space. Reduce notes or target length when needed. The default Qwen preset
uses 16,384 tokens. Context limits and long-form speech limits are separate.

## Voice Studio handoff

**Export for Voice Studio** writes one reviewed UTF-8 TXT, preserving paragraphs.
In Voice Studio's Chatterbox Narration Studio, use **Load script**, select the
TXT and reference voice, then generate speech. For Qwen3-TTS or IndexTTS, copy
the reviewed text to **Voice Engines**.

Automatic long-form chunking is currently in the Chatterbox narration workflow.
This writer does not add chunking to Qwen3-TTS/IndexTTS or change their runtime
limits. The displayed duration assumes 140 spoken words per minute and is not
an inference-time estimate. Bethesda audio conversion still belongs to Voice
Studio's export workflow.

## Classic Generator and existing data

**Classic Generator** preserves the expanded 156-scene library and four complete
authored stories. These finite authored stories are original fan fiction, not AI
outputs or official canon. Classic scene formats retain Short/Medium/Long. Mood
filters, station separation, repetition protection and custom authored ad spots
remain available. Ad Manager may store many spots but selects only one at a time.

Custom ads and history keep the existing profile folder:

- Windows: `%USERPROFILE%\.goodneighbor_blues_dj`
- Linux: `~/.goodneighbor_blues_dj`

AI settings, profiles and continuity are in `ai_studio.json` there. Downloads,
runtime and diagnostic logs are in its `ai_writer` subfolder, separate from all
Voice Studio models and Python environments. The app binds its authenticated
writing server to loopback on a private port and stops its own server after use.

Extract this update into a fresh application folder and keep the existing
profile folder. Set `GOODNEIGHBOR_DJ_HOME` to use an isolated test profile.
`make_content.py` is a legacy 33-scene utility; its output is
`dialogue_base_33.json`, so it cannot overwrite the expanded bundled database.

## Models and runtime

- [Gemma The Writer, Mighty Sword 9B](https://huggingface.co/DavidAU/Gemma-The-Writer-Mighty-Sword-9B-GGUF):
  community Gemma 2 writing-model merge, native Gemma chat template.
- [Qwen3 4B Instruct 2507 GGUF](https://huggingface.co/lmstudio-community/Qwen3-4B-Instruct-2507-GGUF):
  community quantization of the separate Qwen general-purpose instruction model.
  Its preset uses the [original Qwen model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)'s
  recommended temperature 0.7, top-p 0.8, top-k 20 and min-p 0.0.
- [llama.cpp](https://github.com/ggml-org/llama.cpp): pinned official `b11703`
  release assets with checksum verification. No binaries are redistributed here.

Upstream software and model terms apply to their respective downloads. A model's
name or published benchmark does not establish how well it writes these specific
characters. See **AI_GENERATION_CHECK.md** for actual local test results.

## Verification

```bash
python -m unittest tests_engine tests_single_output tests_ai_writer -v
```

Tests use no model downloads. They cover classic regressions, complete stories,
prompt context, download checksums/resume/cancellation, safe extraction, streamed
completion and failure handling, loopback process settings, context limits and
actual Qt background-worker behavior. Real model writing is checked separately.
Windows EXE packaging and AMD GPU inference still require native machine tests.

### Version 0.8.1: speech engines and CPU threads
Speech Director includes Chatterbox Nano (same conservative native event strategy as Turbo). AI Setup includes configurable llama.cpp CPU inference threads. This does not enable simultaneous TTS generation; the Speech Director exports instructions only.


### Version 0.8.2: memory allocation startup repair

AI Setup now has **Disable weight repacking (--no-repack)**, enabled by default
for both new and existing configurations. This avoids the extra CPU_REPACK
weight buffer (3.71 GiB reported with the Gemma 9B GGUF in one Windows failure).
If CPU_REPACK fails while repacking is enabled, the app surfaces a specific
startup explanation. No changes to script-generation behavior or existing
user data are required. If `--no-repack` is unknown, reinstall the
app-provided llama.cpp runtime. PyQt6 UI and a real Windows/GPU/model load
were not available in this build environment, so on-device testing is needed.

If loading continues to fail, close memory-heavy applications, check the
**Committed** amount vs. **Commit limit** under Windows Task Manager >
Performance > Memory, and make sure your page file isn't disabled or tiny.
Reducing the context size helps KV-cache allocation later in startup, but
it does **not** directly fix the CPU_REPACK allocation shown in the log.


## AI writer memory compatibility (v0.8.3)

If `llama-server` fails with `CPU_REPACK` or `failed to allocate buffer for kv cache`, see **MEMORY_RECOVERY.md**. The application now has selectable KV-cache types, automatic reduced-context retries, and a visible warning when a reduced context was used. Model files and saved data are unchanged.

## Windows installer and portable packages

The **DJ Writer Windows installer and portable** Actions workflow builds the
standalone DJ Writer on pushes affecting this tool or the shared writer core,
on pull requests, and through **Run workflow**. It runs the regression suite,
builds the branded EXE, verifies frozen startup/icon loading, and publishes:

- `DJ-Writer-Windows-Installer`: `DJ-Writer-Setup-<version>.exe`
- `DJ-Writer-Windows-Portable`: `DJ-Writer-<version>-Windows-Portable.zip`
- `DJ-Writer-Windows-Checksums`: SHA-256 hashes of both packages.

Both use `VERSION` from `goodneighbor_dj.py`. The installer is per-user, needs
no administrator privileges, and offers an optional desktop shortcut. Both
editions use the existing `~/.goodneighbor_blues_dj` data location; uninstalling
the app preserves settings, libraries and downloaded writing models. Models
are downloaded/configured separately and are not bundled.

Local build: install Inno Setup 6, then run `./plugins/dj-writer/build_windows.ps1`.
Use `-SkipInstaller` for portable only, or `-InnoSetupCompiler <path>` for a
custom compiler location. Install this standalone separately from Voice Studio;
it is distinct from the generic Promotional Writer panel.
# Shared AI library (0.9.3)

DJ state now lives in `%LOCALAPPDATA%\PlaguedAI\apps\dj-writer`, writing models
in `PlaguedAI\models\text`, and reusable runtimes in `PlaguedAI\runtimes\llama.cpp`.
The legacy home remains a compatibility path after consolidation. Existing
custom `GOODNEIGHBOR_DJ_HOME` overrides stay isolated. See the repository's
`SHARED_AI_STORAGE.md` before migrating another machine. Profiles, accepted DJ
character notes and history remain distinct from shared model files.
