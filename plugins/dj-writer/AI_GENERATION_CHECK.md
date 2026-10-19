# AI writing checks, October 17, 2026

These are development smoke checks with real local weights. They verify the
writing path and editorial controls, not a universal ranking of model quality.
The sample drafts still require editing and approval before production.

## Environment

- Linux x64, AMD EPYC host exposing 9 logical CPUs and approximately 9.7 GiB RAM.
- CPU inference through the pinned official llama.cpp b11703 runtime.
- Qwen3-4B-Instruct-2507 community Q4_K_M GGUF, 2,497,280,448 bytes.
- Model SHA-256 verified before loading:
  `8cdb57cbb880d313736a9bc4e3d3d2485f145b5e19cf33783746e753e82641fc`.
- Gemma The Writer Mighty Sword 9B community Q4_K_M was also downloaded and
  checksum verified for an earlier candidate check.

These timings include loading and writing here. They do not predict speed or
memory use on another CPU or the user's RX 7600 XT.

## v0.7.1 blank-request default checks

Three requests ran sequentially through the actual Qt AI Studio worker using
Qwen on CPU, with the extra-direction box left blank. The model used the new
format, station, DJ and advertiser defaults.

| Request | Requested words | Actual words | Time here |
| --- | ---: | ---: | ---: |
| story | 600 | 604 | 79.99 seconds |
| robot ad | 100 | 95 | 26.96 seconds |
| cross promo | 80 | 65 | 25.96 seconds |

The Tin Can Clinic ad named the business and described robot repairs. The cross-
promo named Goodneighbor Blues and 95.77 while retaining Plague as its host.
Each job replaced the single editor result, added exactly one completed history
entry, left review unchecked and left narration export disabled. The three
unedited samples are `examples/default_story_unreviewed.txt`,
`examples/default_robot_ad_unreviewed.txt` and
`examples/default_cross_promo_unreviewed.txt`.

These are functioning generation checks, not approved examples of canon or
literary quality. The story made unsupported pre-war claims about mutfruit and
a character, and its setting logic still needs editing. The final lore template
was strengthened afterward to address chronology and invented services at known
landmarks. That final wording is covered by prompt-assembly tests; another
model benchmark was not run for the wording change. Earlier development drafts
also invented ad hours/locations and confused brahmin with machines. The default
closing line, explicit setting definitions and review flags were tightened in
response. No automatic check catches every such error.

Unapproved history text is no longer supplied to the model as context. Only
editor-maintained notes provide ongoing continuity; history still supports
post-generation repetition checks. The Qwen preset follows the original model
card's recommended temperature, top-p, top-k and min-p settings. The full prompt
catalog is in `PROMPT_DEFAULTS.md`.

## Earlier v0.7.0 Qwen writing results

| Request | Requested words | Actual words | Time here | Outcome |
| --- | ---: | ---: | ---: | --- |
| Plague story about a repaired toy bird | 600 | 612 | 70.33 seconds | Natural end, six paragraphs, one script |
| Hattie commercial for Mirelight Repairs | 100 | 72 | 18.09 seconds | One spot, exact brand name and slogan; length shortfall flagged |

The story exercised host profile, shared setting, a disproven theory and an
unresolved plot thread. Its generated repair backstory and implied observations
still need continuity review. Basic validation cannot establish lore correctness
or literary quality. The exact generated draft is in `examples/ai_story_draft.txt`.

The commercial ran through the actual Qt AI Studio controls and background
worker, streamed into one editor, and retained the supplied slogan **We keep
the night talking.** It produced 72 words, so the editor warned that it was shorter
than the requested 100. There was exactly one history entry. Review remained
unchecked and export remained disabled. The exact unedited output is in
`examples/ai_commercial_draft.txt`.

The output samples have not been marked approved, synthesized, or added to a
Voice Studio production library.

## Story-specialist candidate

Gemma The Writer Mighty Sword 9B completed an earlier 600-word story request
with 300 words in 100.32 seconds. The application flagged that shortfall.
Its earlier commercial changed the required slogan from “We” to “They”; the
updated validator now explicitly catches missing or changed brand slogans.
A later long-story retry was stopped after generation became slow. It is not
counted as a completed result. These checks used evolving prompts and do not
constitute a controlled comparison against Qwen.

Qwen is the current CPU starting preset. Gemma remains an optional larger story
candidate. Additional story specialists need their own content and hardware
checks. No claim of a best storytelling model is made by this update.

## Automated checks

78 unit and offscreen Qt checks passed with:

```bash
python -m unittest tests_engine tests_single_output tests_ai_writer -q
```

Coverage includes the retained expanded scene library and ads, whole authored
stories, one-result editing/history, prompt conditioning, profile persistence,
resume/checksum/cancellation, archive traversal rejection, authenticated loopback
startup, streaming completion and broken connections, native/request context
limits, cancellation/failure restoration, review invalidation and UTF-8 export.
A history-save failure is surfaced without losing the visible script. New coverage checks all nine formats for all three DJs, bundled advertisers, station/frequency separation, optional-brief behavior, prompt viewing without a model, preservation of custom notes, and supported versus invented ad details. Unapproved history is excluded from prompt lore.

## Remaining machine checks

Both official Windows CPU and Vulkan runtime archives passed SHA-256 checks
and unpacked through the application installer, including their companion DLLs.
Native Windows executable packaging/launch and AMD Vulkan inference were not
run here. Longer 2,000-word inference was not benchmarked. The context-budget
checks are tested, but long-form text quality and subsequent TTS chunking remain
separate checks. Voice Studio's speech environments and stable v0.2.4 were not
modified by this writer update.
