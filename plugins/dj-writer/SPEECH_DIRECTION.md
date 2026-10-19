# Speech-ready output — version 0.8.5

The **Speech-ready output** checkbox is on by default, and **Chatterbox Turbo** is
selected by default. As the AI writer streams, a throttled (~350ms) preview in
the editor shows the **engine-ready script**. The finished draft is always
rerendered from the writer's original raw text, so no generated speech cue is
fed into the model, duplicated or lost. This applies to AI Studio and
Classic Generator. The writer continues to produce clean spoken words internally;
the speech layer is applied after generation. Existing accidental writer-produced
`[dialog]` or repetitive `[advertisement]` labels are normalized first. Scripts in history remain clean, so
they can be reused with a different speech engine without carrying stale tags.

## How to use

1. Choose your DJ, format, and **Narration engine** before generating.
2. Generate. With Turbo or Nano, contextual native tags appear in the editor.
   The text in **Export for Voice Studio** is the edited, tagged text you see.
3. Review/fix your script before checking **I have reviewed this script**.
4. If you change engine or intensity, use **Apply cues to script** on the current
   edited text. This strips previously generated native tags and regenerates
   appropriate ones. The review check is cleared when the script changes.
5. For complete control, insert any native Chatterbox tag at the cursor with
   **Insert tag at cursor**. Manually authored valid native tags are preserved
   when the same engine's package is exported.
6. For IndexTTS 2.5 and official Qwen3-TTS, the editor contains clean speech.
   Use **Export TTS package** for the per-segment emotion vectors / instruction
   manifest. Voice Studio needs a separate adapter to consume this JSON; the
   writer doesn't synthesize audio or modify Voice Studio.

## Exact 19 native Chatterbox Turbo/Nano tags

Delivery and emotion (10):
`[angry]` `[fear]` `[surprised]` `[whispering]` `[advertisement]`
`[dramatic]` `[narration]` `[crying]` `[happy]` `[sarcastic]`

Vocal events (9):
`[clear throat]` `[sigh]` `[shush]` `[cough]` `[groan]`
`[sniff]` `[gasp]` `[chuckle]` `[laugh]`

**Not native:** `[dialog]`, `[dialogue]`, `[clear_throat]`, `[whisper]`, `[pause]`.
The writer removes recognized non-speech labels. Exact spelling matters.

## Placement policy

- An atmospheric ad can begin `[narration]`; the first actual pitch gets one
  `[advertisement]`. A genuinely ironic punchline may get `[sarcastic]`.
- Stories receive an opening `[narration]`, with occasional style changes when
  text supports them. In a personal, painful scene, Tal or Hattie may lower the
  delivery using `[whispering]`. Select **Subtle** to suppress inferred whispers.
  Descriptions of a sick child do not produce narrator `[cough]` events.
  Word-for-word story text and original paragraph boundaries are retained. Ad tags are not spammed on every line.
- Sound effects are rare and contextually chosen; the full inventory is manually
  selectable. There is no random sprinkling of groans, cries, or laughter.
- The composer never adds new spoken facts or changes an advertiser name.
- Native tags are distinct from general writing categories. IndexTTS and Qwen3
  do **not** receive Chatterbox brackets as spoken text.

**Caveat:** The 19 tags are tokenizer recognized in ResembleAI's Turbo
vocabulary, but results vary across backends. The upstream Python demo explicitly
uses `[chuckle]` with Nano. One MLX implementation reports the ten style tags
have no audible effect while the nine sound tags work, whereas ONNX users report
more extensive effects. Verify audibility with your particular Voice Studio
backend. The writer can't make an unsupported inference implementation obey tags.

References:
- https://huggingface.co/ResembleAI/chatterbox-turbo/blob/main/added_tokens.json
- https://github.com/resemble-ai/chatterbox/blob/master/example_tts_nano.py
- https://github.com/resemble-ai/chatterbox/issues/492
- https://github.com/resemble-ai/chatterbox/issues/557
- https://github.com/index-tts/index-tts
- https://github.com/QwenLM/Qwen3-TTS
