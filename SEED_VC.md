# Optional Seed-VC for Speak As

Speak As can use a separately installed **Seed-VC V1 F0-auto** runtime to
convert a recorded performance into a saved reference voice. It operates on
audio directly, without an ASR transcript or text re-synthesis. The app prefers
Seed when all four local configuration fields below are supplied. Chatterbox
direct conversion and IndexTTS transcription + re-synthesis remain available.

This integration ships an original subprocess adapter that invokes the installed
upstream inference API. It does not bundle Seed-VC source, Python environments,
model weights or the trial recordings. The feature performs no automatic
installation or model download. See [SPEAK_AS.md](SPEAK_AS.md) for recording,
cancellation, playback and permanent-save controls.

## Fixed profile and behavior

- V1 F0 conditioning enabled, automatic F0 adjustment enabled.
- Length adjustment `1.0`, additional semitone shift `0`.
- 30 diffusion steps and classifier-free guidance rate `0.7`. Random seed `1709`
  matches the reviewed trial and is reset for each take.
- 44,100 Hz output.
- Both source and reference must contain detectable voiced speech. An unvoiced
  input is rejected with an error rather than silently changing engine or
  disabling pitch conditioning.
- The automatic F0 adjustment shifts the source's pitch register toward the
  reference. A zero additional semitone shift does **not** mean unchanged pitch.
  Timing, pitch detail, loudness, consonants and vocal identity can still change;
  exact performance or voice fidelity is not guaranteed.
- The adapter prepares the first 10 seconds as mono 44.1 kHz PCM, matching the
  reviewed trial. The saved original reference file is not edited. Use a reference
  that begins with clean, representative speech.
- If the model waveform's absolute peak exceeds 0.999, one uniform gain
  reduction provides PCM headroom and avoids hard clipping. The status and result metadata disclose it.
  This is not pitch correction, dynamic compression or loudness matching.
- Cold loading and unfamiliar audio shapes can take several minutes. The Seed
  stage watchdog is 10 minutes. The normal 60-second warm-model idle period and
  Cancel / close / device-change release behavior still apply.
- CPU and GPU are explicit choices. A requested unavailable GPU produces an
  error, not an automatic CPU fallback. The integration does not impose GPU
  temperature, power, clock, fan, compute-unit or utilization limits.

## Existing-runtime configuration

Supply an object of string values using `PVS_SPEAK_AS_CONFIG` or the existing
application-data `speak_as.json` described in [SPEAK_AS.md](SPEAK_AS.md). All four
Seed fields are required:

```json
{
  "seed_python": "/absolute/path/seed-runtime/.venv/bin/python",
  "seed_repo": "/absolute/path/seed-runtime/seed-vc",
  "seed_cache": "/absolute/path/seed-runtime/cache",
  "seed_manifest": "/absolute/path/seed-runtime/model-manifest.json"
}
```

- `seed_python`: the executable in the separately managed Python environment
  containing Seed-VC's dependencies and a PyTorch build suitable for the chosen
  CPU, CUDA or ROCm device. Do not substitute Voice Studio's frozen executable.
- `seed_repo`: the upstream checkout containing `inference.py`, its modules,
  configurations and the populated Hugging Face `checkpoints/` cache.
- `seed_cache`: the runtime's auxiliary cache root, separate from the model
  snapshots in `seed_repo/checkpoints`. It must be writable for inference
  caches. It is the trial layout's `cache` directory, not `cache/hf`.
- `seed_manifest`: the local JSON asset manifest recording repositories,
  revisions, declared licenses, filenames, local paths, byte sizes and SHA-256
  hashes. Required V1 assets are validated against it. Keep the local paths
  accurate if the runtime is moved.

The adapter uses local model snapshots with offline Hugging Face/Transformers
loading. It does not follow a floating remote revision during conversion.
Missing, incompatible or invalid assets must be repaired in the separate runtime;
an incomplete configuration is not an instruction to download models. Configuring
Seed does not install or modify the other speech engines.

### Preparing a separate runtime

1. Review the upstream [Seed-VC instructions](https://github.com/Plachtaa/seed-vc)
   and the license sources below. Prepare its checkout and an isolated Python
   environment outside the Voice Studio bundle, using dependencies appropriate
   for the target hardware.
2. Obtain the required V1 assets separately from their official model repositories
   at the recorded revisions. Keep their cards, licenses, configurations and
   tokenizer/feature-extractor files, not just the large weight files.
3. Populate the checkout's local checkpoint cache and an accurate asset manifest,
   and create a writable auxiliary cache root. Use the verified local trial
   layout when available. Voice Studio does not provide an automatic Seed
   bootstrap/download step.
4. Add the four absolute paths to the Speak As configuration and select the
   intended device. Use a short voiced recording and a reference you have
   permission to use. Check the result before relying on it.

The reviewed Debian trial used Python 3.11, PyTorch/torchaudio 2.8.0 + ROCm 6.4,
Transformers 4.46.3, NumPy 1.26.4 and SoundFile 0.12.1. This records a tested
environment, not a promise of compatibility with arbitrary package upgrades or
other platforms.

## Reviewed provenance and license scope

Review date: **2026-11-11**. Source baseline:
[Plachtaa/seed-vc at 51383efd921027683c89e5348211d93ff12ac2a8](https://github.com/Plachtaa/seed-vc/tree/51383efd921027683c89e5348211d93ff12ac2a8).
Its root [LICENSE](https://github.com/Plachtaa/seed-vc/blob/51383efd921027683c89e5348211d93ff12ac2a8/LICENSE)
contains GNU GPL version 3. The local V1 checkout changes one cache assignment
in `inference.py` to preserve an externally supplied `HF_HUB_CACHE`.
The same isolated checkout also has V2 loader/precision compatibility changes;
those are not the selected V1 inference profile and are not bundled by this
integration. Keep any separately distributed modifications identified and
supply the applicable source and notices.

The selected V1 assets were read from the pinned local model cards and manifest.
All 23 V1 model/configuration/card/license files recorded for the five repositories
below were checked against the recorded sizes and SHA-256 hashes. The trial
manifest additionally contains V2 assets; that does not make V2 or its additional
models part of this profile.

| V1 dependency and evidence | Pinned repository revision | Declared license |
| --- | --- | --- |
| [Seed-VC checkpoint and config](https://huggingface.co/Plachta/Seed-VC/blob/257283f9f41585055e8f858fba4fd044e5caed6e/README.md) | `257283f9f41585055e8f858fba4fd044e5caed6e` | Model-card metadata: GPL-3.0 |
| [Whisper-small content encoder](https://huggingface.co/openai/whisper-small/blob/973afd24965f72e36ca33b3055d56a652f456b4d/README.md) | `973afd24965f72e36ca33b3055d56a652f456b4d` | Model-card metadata: Apache-2.0 |
| [CAMPPlus speaker encoder](https://huggingface.co/funasr/campplus/blob/e4b6ede7ce16997aff4ae69fbca1f0175e2afede/README.md) | `e4b6ede7ce16997aff4ae69fbca1f0175e2afede` | Model-card metadata: Apache-2.0 |
| [NVIDIA BigVGAN 44 kHz vocoder](https://huggingface.co/nvidia/bigvgan_v2_44khz_128band_512x/blob/95a9d1dcb12906c03edd938d77b9333d6ded7dfb/LICENSE) | `95a9d1dcb12906c03edd938d77b9333d6ded7dfb` | MIT; full license names NVIDIA CORPORATION, 2024 |
| [RMVPE pitch checkpoint supplied by lj1995/VoiceConversionWebUI](https://huggingface.co/lj1995/VoiceConversionWebUI/blob/e6d0c1a17da07c33557852f9dfa2bd44cc75737d/README.md) | `e6d0c1a17da07c33557852f9dfa2bd44cc75737d` | Model-card metadata: MIT |

Despite `whisper_base` appearing in the Seed checkpoint/config filenames, the
reviewed configuration explicitly loads **openai/whisper-small**. The license
entry above describes that Hugging Face artifact's declaration, not all Whisper
implementations or releases. The Seed and RMVPE cards contain only minimal
metadata. Their metadata is evidence of the repositories' declared terms, not
an independent verification of every upstream contribution or training right.

Principal weight hashes, from the verified manifest:

| File | SHA-256 |
| --- | --- |
| `DiT_seed_v2_uvit_whisper_base_f0_44k_bigvgan_pruned_ft_ema_v2.pth` | `42aef93ffe65857c840d270252fa040f7ba04514945ec460f3ac1ac2a96de684` |
| `openai/whisper-small/model.safetensors` | `1d7734884874f1a1513ed9aa760a4f8e97aaa02fd6d93a3a85d27b2ae9ca596b` |
| `campplus_cn_common.bin` | `3388cf5fd3493c9ac9c69851d8e7a8badcfb4f3dc631020c4961371646d5ada8` |
| `nvidia/bigvgan_v2_44khz_128band_512x/bigvgan_generator.pt` | `d9fe7ec6bd0b44ed9d66973d5012d8181c1570b01e5c72df51973e241dccd357` |
| `rmvpe.pt` | `6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193` |

Use the local manifest as the complete asset inventory, including tokenizer and
configuration files, rather than relying only on these principal-weight identifiers.

The original Voice Studio integration source retains the project's MIT license.
The distributed GUI binary remains GPLv3 because it includes GPL PyQt6, as
documented in [BINARY_LICENSE.md](BINARY_LICENSE.md). Neither fact relicenses the
separate Seed runtime, third-party code, weights or generated output.
Subprocess separation describes the implementation; it is not a legal
determination that copyleft obligations cannot apply.

This is a scoped provenance review, **not a complete legal compliance audit** or
clearance to distribute a combined runtime/model bundle. Redistribution requires
reviewing the exact components, modifications, applicable license texts,
copyright/attribution notices and corresponding-source obligations. Model
licenses do not grant rights to another person's voice, recordings or identity.

## Evidence and limits

The separate Debian/ROCm trial included a user-supplied natural recording of
approximately 11.603 seconds; V1 F0-auto produced about 11.598 seconds, approximately 5 ms
shorter. That one fixture supports close duration retention, not exact timing,
pitch, loudness or identity preservation across voices and recordings. This
integration review did not perform a new live-microphone test.

In earlier isolated measurements a repeated 4.23-second fixture took about
13 seconds warm, after a roughly 132-second cold request. The natural fixture's
request took about 214 seconds. Different audio shapes can trigger more backend
initialization even with a loaded model. These are observations from the local
trial, not guaranteed application response times or a real-time claim.
