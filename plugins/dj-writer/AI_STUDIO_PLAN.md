# AI Studio implementation status, v0.7.1

The separate local writing engine and predefined Fallout prompts are implemented.
Every script format has a built-in default, with station identities, DJ
personalities, lore boundaries and advertiser background supplied automatically.
An optional brief adds direction, and View writing prompt exposes the active
guidance before inference. See PROMPT_DEFAULTS.md for the full catalog.

The writing engine creates one draft per
request, with editable DJ profiles, setting/lore, manual continuity notes,
advertiser descriptions/slogans, a brief and target word count. It retains the
Classic Generator, expanded database, whole authored stories and Ad Manager.

Qwen3 4B Instruct Q4_K_M is the CPU starting preset, verified with real story
and commercial generation. Gemma The Writer, Mighty Sword 9B Q4_K_M is an
optional story candidate. An existing compatible
writing GGUF can be selected manually. Voice Studio's installed Qwen3-TTS weights
remain speech-only. Runtime/model installers, streaming, cancellation, review
checks and UTF-8 script handoff are included. See README.md for operation and
AI_GENERATION_CHECK.md for measured validation.

The editor still controls whether a script is ready for narration. New inventions
do not update continuity automatically. Simple validation is not a canon or
contradiction checker. TXT export is a manual handoff, not an automatic speech
queue. No Voice Studio or speech-engine dependency is installed or modified.

Future work may compare additional story specialists, add stronger continuity
tools and provide a richer approved-script handoff. Those are separate from this
working single-script generation path. Model quality and AMD acceleration need
the user's content and machine tests; never infer them from TTS success.
