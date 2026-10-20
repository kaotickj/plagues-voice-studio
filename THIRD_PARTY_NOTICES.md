# Third-party notices

Plague's Voice Studio was created by Kaotick Jay. It is an independent graphical frontend, not an official Resemble AI product.

- **Chatterbox** by Resemble AI: MIT-licensed source, audio watermarking retained.
  https://github.com/resemble-ai/chatterbox
- **Model weights**: distributed separately by Resemble AI via Hugging Face.
  Review license/model cards and usage conditions before redistributing bundles.
- **PyTorch**: BSD-style license, https://pytorch.org/
- **PyQt6**: GPL v3 or commercial licensing, https://www.riverbankcomputing.com/software/pyqt/
  IMPORTANT: This project is distributed as GPL-compatible source when using GPL PyQt6;
  distributing closed-source binaries requires appropriate PyQt6 commercial licensing.
- **FFmpeg binary via imageio-ffmpeg**: governed by the specific packaged FFmpeg build
  license (may be LGPL or GPL); review and supply notices/source offers as required.

Before distributing a binary, review licenses for all bundled libraries and model weights.
The example installer copies this notice; it is not a complete legal compliance audit.

### Optional Bethesda voice-export integration (v0.2.1)

- WMAEncodeRS: MIT license, https://github.com/MSIVST/WMAEncodeRS . NOT BUNDLED. Uses Windows Media runtime.
- Nukem9 FaceFXWrapper: https://github.com/Nukem9/FaceFXWrapper . NOT BUNDLED. Its license expressly acknowledges use of Bethesda Creation Kit code and subject matter; do not presume the entire compiled tool is freely redistributable.
- Bethesda `FonixData.cdf`, Creation Kit and `xwmaencode.exe`: Bethesda-controlled assets and tools; NOT BUNDLED. Installed locally by the end user.
- Optional clean-room OpenFaceFX: https://github.com/OpenFaceFX/OpenFaceFX (MIT); its Bethesda LIP writer remains experimental, no in-game verification and no Fallout 4 support as of this review. Not used or bundled.
- `.fuz` packing implementation and test code are original Python source distributed with this project.

### Optional speech engines in experimental 0.3.0-alpha1

- **Qwen3-TTS**, developed by Qwen/Alibaba, https://github.com/QwenLM/Qwen3-TTS . Separate source/model terms apply; not included in the host package. Optional explicit installation by the user.
- **IndexTTS 2.5**, developed by IndexTTS upstream, https://github.com/index-tts/index-tts . Code/models are released under the Bilibili Model Use License Agreement; read the official LICENSE and DISCLAIMER. Not bundled. An optional setup script requires the user's license review acknowledgement.
- The optional-engine subprocess runners are original integration code; they do not confer any licensing or redistribution rights to the upstream packages, models or generated output.

### Promotional Writer plugin

- Local writing inference uses a separately downloaded **llama.cpp** runtime:
  https://github.com/ggml-org/llama.cpp . Runtime and model files are not bundled
  with the source plugin. The setup UI exposes the upstream project/model links.
- Optional text models are community GGUF releases of **Gemma The Writer Mighty
  Sword 9B** (https://huggingface.co/DavidAU/Gemma-The-Writer-Mighty-Sword-9B-GGUF)
  and **Qwen3 4B Instruct**
  (https://huggingface.co/lmstudio-community/Qwen3-4B-Instruct-2507-GGUF).
  Review the respective upstream model terms; speech model downloads are separate.
- Plugin integration and copywriting recipes: Kaotick Jay / Plagued Mods.
  The themed DJ Writer standalone is not part of the generic host plugin bundle.

### DJ Writer optional wiki reference lookup

DJ Writer can fetch article introductions from the Independent Fallout Wiki
(https://fallout.wiki/). Wiki reference text is downloaded only on lookup and
cached in the user's DJ Writer data directory; it is not bundled in the host
or standalone package. Cached entries retain source URLs, revision IDs,
contributor attribution and the site's reported license metadata (currently
Creative Commons Attribution-ShareAlike 4.0). Review the linked source/history
and license when reusing reference prose. Original curated notes in the writer
are concise factual summaries with source links. Generated drafts are never
silently promoted to wiki facts or saved reference entries.
