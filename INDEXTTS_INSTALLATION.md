# IndexTTS 2.5: Windows and Linux installation

Reviewed October 26, 2026 for the **local Voice Studio 1.0.0rc4 candidate**.
This guide is unpublished. Linux dependency installation, the installed Studio
adapter import, verified model staging and offline text normalization passed.
**Linux Index model loading and short GPU synthesis passed** through the actual
installed Studio adapter, including observed GPU execution through BigVGAN.
The 4.23-second Mama Mire-reference WAV was finite with no full-scale clipped
samples. The creator listened and accepted this exact sample. Windows speech worked
on the creator's earlier installation, but a fresh Windows installation of the
exact revision below has not been tested. These are separate evidence scopes.

## Requirements and isolation

- Use the [official Index repository](https://github.com/index-tts/index-tts),
  pinned at `d9e41aac89fd00b3d71497fddb287b7f24613712`.
- Python **3.10 or 3.11** is required: the pinned project declares `>=3.10,<3.12`.
  This Linux installation uses **3.11.17**. Do not reuse the Python 3.13
  Chatterbox/Qwen environment or install into the application's frozen bundle.
- The API is `indextts.infer_v2_5.IndexTTS2`. The package's distribution version
  still says `indextts 2.0.0`; that does not mean the 2.5 API/model is absent.
- Torch and torchaudio must match **2.8.x** and the same CPU/CUDA/ROCm backend.
  Install backend packages before accepting the rest of the dependency closure.
- Git, an isolated Python environment and enough healthy local storage are
  needed. Models total approximately **7.08 GB** before licenses and small
  metadata. The measured Linux setup received **11.65 GB / 10.85 GiB** including
  Python, dependencies and models, and allocated **27.71 GB / 25.81 GiB** before
  small frontend caches. It retained wheel staging and build inputs for recovery.
  Reserve **40 GiB working space**, plus at least **20 GiB free** on this machine.
  This is a measured Linux allowance, not a Windows download-size guarantee.
- Read the repository/model licenses before use. The Index license is distinct
  from the MIT/Apache licenses of auxiliary assets. Do not redistribute a model
  merely because the application is distributable.

## Windows: official dependency route

These commands describe the pinned official route; they have **not** been rerun
on a clean Windows machine for RC4. Use PowerShell, an installed Git and
[uv from its official installation guide](https://docs.astral.sh/uv/getting-started/installation/).
Do not bypass PowerShell policy or install driver changes merely to follow this page.

```powershell
git clone https://github.com/index-tts/index-tts.git "$env:LOCALAPPDATA\PlaguedAI\engines\index-tts"
Set-Location "$env:LOCALAPPDATA\PlaguedAI\engines\index-tts"
git checkout --detach d9e41aac89fd00b3d71497fddb287b7f24613712
git rev-parse HEAD
uv python install 3.11.17
uv sync --python 3.11.17 --frozen
uv pip check --python .\.venv\Scripts\python.exe
```

`uv sync` creates `.venv` at this final location. Do not move an existing venv.
Managed Python comes from uv's documented standalone distribution; there is no
assumption that python.org supplies a Windows 3.11.17 installer.

The pinned project's default Linux/Windows Torch source is the official
**NVIDIA CUDA 12.8 wheel index**. It does not implement Windows AMD ROCm or
Vulkan. Check your NVIDIA device/driver against the official PyTorch/NVIDIA
requirements before choosing that route. CUDA software cannot make a Radeon
GPU supported. CPU use needs a separately resolved matching CPU Torch lock or
wheel set; do not install CUDA dependencies and call that a CPU-only recipe.

The base `uv sync --frozen` deliberately omits `--all-extras`. Voice Studio does
not require the Index WebUI. DeepSpeed, flash-attn, custom fused CUDA kernels,
torch.compile and emotion-text Qwen are disabled by its conservative adapter.
Do not add them to fix an unrelated import error. Windows uses **wetext**;
Linux uses **WeTextProcessing** through upstream platform markers.

## Linux: NVIDIA versus the measured AMD installation

For a compatible NVIDIA system, the same pinned repository and base
`uv sync --python 3.11.17 --frozen` route uses upstream's CUDA wheel source.
Use `.venv/bin/python` instead of the Windows interpreter path. Fresh NVIDIA
installation and generation were not tested in this RC4 Linux exercise.

**Do not run that CUDA-default sync over the AMD environment below.** The
measured AMD setup was built separately with a reviewed offline closure:

| Component | Exact installed selection |
| --- | --- |
| Python | CPython 3.11.17, Astral standalone release `20261021` |
| Torch | `2.8.0+rocm6.4`, official PyTorch cp311 Linux wheel |
| torchaudio | `2.8.0+rocm6.4`, matching official wheel |
| Triton provider | `pytorch-triton-rocm==3.4.0` |
| Important frontend packages | Transformers 4.52.1; WeTextProcessing 1.0.4.1; g2p-en 2.1.0; NLTK 3.9.1 |
| GPU extensions | DeepSpeed, flash-attn, custom CUDA kernels and torch.compile disabled |

The host already had its AMD kernel driver. This operation did **not** install
drivers, change system Python, spoof GPU identity or change other engine venvs.
The RX7600XT/Debian combination passed one bounded real GPU test and remains
experimental; this does not establish all languages, references or long scripts.
PyTorch ROCm deliberately exposes devices through `torch.cuda`; the API name
does not turn HIP into NVIDIA CUDA. This is **not Vulkan**.

The actual installation order was:

1. Verify the standalone Python archive and official Torch/torchaudio/Triton
   wheels; create the new venv at its final path.
2. Check out only the pinned official source. Read its `pyproject.toml` and
   `uv.lock`; select Python 3.11 Linux resolution markers. The lock has multiple
   scipy/networkx/contourpy/IPython entries for different Python branches.
3. Hash-check/review source-only antlr4-python3-runtime 4.9.3, argbind 0.3.9,
   Distance 0.1.3, jieba 0.42.1, julius 0.2.7, openai-whisper 20250625,
   randomname 0.2.1 and unidic-lite 1.0.8. Build with verified setuptools/wheel/
   hatchling tooling, offline, using `pip wheel --no-index --no-deps
   --no-build-isolation`. No APT/compiler setup was required in this run.
4. **AMD packaging exception:** Whisper's Linux metadata requests generic
   `triton>=2`; AMD Torch uses `pytorch-triton-rocm`, which supplies the same
   import namespace. The local Whisper wheel changes only that dependency
   metadata to the official AMD provider. Its tokenizer/inference Python code
   is unchanged. Installing both Triton distributions is not the solution.
   This exception does not apply to the Windows recipe above.
5. Resolve the complete constrained closure without installing it; verify
   every final wheel's publisher URL, size and SHA-256. Install those **126
   exact wheels** offline with `python -m pip install --no-index --no-deps
   --no-compile <verified-wheel-paths>`, then run `python -m pip check`.
6. Test the actual Studio adapter import and API, stage verified models below,
   then initialize the text frontend offline. Only then attempt model loading.

This describes the actual advanced AMD procedure, not an untested one-line
AMD installer. Its receipts and reviewed build inputs are retained locally in
`indextts-linux-setup-20261026` and `indextts-linux-plan-20261026` under the Codex
task directory. Do not execute unknown cached wheels or follow floating source
dependencies to reproduce it. A redistributable AMD setup helper is not yet
qualified.

## Model downloads, revisions and layout

Use the [official Index model](https://huggingface.co/IndexTeam/IndexTTS-2.5)
at revision `c39ce5ba981572cb187443877ff559dfb246ce63`.
Do not mix its config with IndexTTS-2 or download the whole optional Qwen
emotion-text model: Studio uses `use_qwen_emo=False`.

Install the official CLI separately with `uv tool install "huggingface-hub==0.35.0"`
and follow its printed PATH instructions. With the CLI available, choose `checkpoints` as the main
destination and download the listed files at the exact revisions. For example:

```text
hf download IndexTeam/IndexTTS-2.5 --revision c39ce5ba981572cb187443877ff559dfb246ce63 --local-dir checkpoints --include config.yaml codec.pth gpt.pth s2mel.pth feat1.pt feat2.pt wav2vec2bert_stats.pt multilingual_zh_ja_yue_char_del.tiktoken LICENSE README.md
hf download facebook/w2v-bert-2.0 --revision da985ba0987f70aaeb84a80f2851cfac8c697a7b --local-dir checkpoints/hf_cache/w2v-bert-2.0 --include config.json preprocessor_config.json model.safetensors README.md
hf download funasr/campplus --revision e4b6ede7ce16997aff4ae69fbca1f0175e2afede --local-dir checkpoints/hf_cache --include campplus_cn_common.bin
hf download nvidia/bigvgan_v2_22khz_80band_256x --revision 633ff708ed5b74903e86ff1298cf4a98e921c513 --local-dir checkpoints/hf_cache/bigvgan --include config.json bigvgan_generator.pt LICENSE README.md
```

Preserve each publisher's license/model card. CAMPPlus's model card identifies
Apache-2.0. The [pinned manifest](docs/index25-model-manifest.json) lists sizes,
publisher LFS SHA-256 and Git blob identities. Verify hashes before loading:
PowerShell `Get-FileHash -Algorithm SHA256 <file>` or Linux `sha256sum <file>`.
For small files with only Git blob identities, compare against the exact pinned
repository blob; a Git blob SHA-1 includes the `blob <length>\0` header and is
not the raw file SHA-1. Never waive a mismatch. An incomplete transfer is not a
valid weight file; resume through the publisher and verify the full result.

The required layout is:

```text
checkpoints/
  config.yaml                         # version: 2.5
  codec.pth  gpt.pth  s2mel.pth
  feat1.pt  feat2.pt  wav2vec2bert_stats.pt
  multilingual_zh_ja_yue_char_del.tiktoken
  hf_cache/
    w2v-bert-2.0/{config.json,preprocessor_config.json,model.safetensors}
    campplus_cn_common.bin
    bigvgan/{config.json,bigvgan_generator.pt}
```

Prestage the auxiliary assets. Otherwise upstream may attempt downloads during
initialization. Do not treat a successful small import probe as an offline-ready
model. In this Linux setup `repo/checkpoints` links to the canonical Linux model
directory; the original tracked `pinyin.vocab` directory is preserved separately.

## Configure Voice Studio and verify

Open **Voice Engines**, select **IndexTTS 2.5** and enter:

| Field | This Linux installation | Windows default from the recipe |
| --- | --- | --- |
| IndexTTS Python | `/home/kaotickj/.local/share/PlaguedAI/runtimes/index-tts-2.5/.venv/bin/python` | `%LOCALAPPDATA%\PlaguedAI\engines\index-tts\.venv\Scripts\python.exe` |
| IndexTTS repository | `/home/kaotickj/.local/share/PlaguedAI/engines/index-tts` | `%LOCALAPPDATA%\PlaguedAI\engines\index-tts` |
| Model location | `/home/kaotickj/.local/share/PlaguedAI/models/index-tts/2.5`, linked as `repo/checkpoints` | `repo\checkpoints` |

Click **Save runtime paths**, reopen the tab, then **Test selected engine**.
Python fields require an executable, not JSON, a model directory or a Windows
interpreter on Linux. The repository must contain `indextts` and accessible 2.5
checkpoints. These Linux paths do not depend on a mounted Windows volume.

For a terminal import check, run the configured interpreter with:

```python
import torch
from indextts.infer_v2_5 import IndexTTS2
print(torch.__version__, torch.version.hip, torch.cuda.is_available())
```

An import pass establishes package readiness only. To qualify speech, close or
finish other heavy generators, select an authorized reference, English, neutral
emotion and duration factor 1.0, and generate one short ordinary sentence to a
new WAV. Use explicit CPU for a CPU runtime. The current optional-engine compute
menu's `NVIDIA CUDA` label is legacy wording. Choose **Auto** with this verified
ROCm interpreter; qualification explicitly required GPU and refused CPU fallback.
An AMD qualification must confirm the HIP backend and actual GPU execution
through the vocoder, plus a completed finite WAV. Auto/import-ready labels alone
are insufficient. Do not silently label CPU fallback as GPU.

## Troubleshooting and recovery

- **Python 3.12/3.13 dependency errors:** use a separate supported 3.10/3.11 venv.
- **`infer_v2_5` absent:** check the source commit and interpreter import path;
  don't substitute the older `infer_v2` interface.
- **Missing config/auxiliary model:** verify the layout and hashes, not just
  the presence of the large GPT weight. Leave existing models intact.
- **CUDA/HIP error:** report the actual Torch build, driver/device and failure
  stage. NVIDIA CUDA, AMD ROCm and native Vulkan are different backends.
  No working native Vulkan Index route is qualified by this guide.
- **Frontend startup is slow:** Linux builds its Chinese finite-state cache
  once. The observed offline initialization took about 40 seconds; cache
  construction is not voice-model inference.
- **NLTK resource error:** obtain only the named official resource with a
  verified identity; don't enable broad automatic first-run downloads.
- **Duration control:** `duration_factor > 1` means longer/slower, not faster.
- **Failed setup:** restore the previously saved runtime paths or leave Index
  unset. The new source/runtime/models are separate from Chatterbox, Qwen,
  Kokoro and user audio. Do not delete those assets to repair Index.

Successful metrics do not prove naturalness or voice fidelity. Listen to the
finished WAV before accepting its pronunciation, omissions/repeats, pacing and
speaker identity. The creator accepted the short Linux Index sample; longer/different passages remain unqualified. The first
instrumented qualification took 119.66 seconds overall, including 23.07 seconds
in model initialization; upstream reported 79.30 seconds inference for 4.23
seconds audio. Peak process RSS was 8.70GiB and peak Torch GPU allocation 6.04GiB.
MIOpen workspace warnings occurred but the run completed. These cold,
instrumented timings are not a production benchmark or evidence of a speedup
over CPU. No CPU comparison or second render was run.
