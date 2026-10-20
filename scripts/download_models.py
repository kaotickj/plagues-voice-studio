"""Download Chatterbox models to self-contained directories for bundling.

Usage: python scripts/download_models.py nano turbo english multilingual-v3
Requires: huggingface_hub. Downloading full weights can use several GB.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))

MODEL_SPECS = {
    "nano": ("ResembleAI/chatterbox-nano", ["*.safetensors", "*.json", "*.txt", "*.pt", "*.model"]),
    "turbo": ("ResembleAI/chatterbox-turbo", ["*.safetensors", "*.json", "*.txt", "*.pt", "*.model"]),
    "english": ("ResembleAI/chatterbox", ["ve.safetensors", "t3_cfg.safetensors",
              "s3gen.safetensors", "tokenizer.json", "conds.pt"]),
    "multilingual-v3": ("ResembleAI/chatterbox", ["ve.pt", "s3gen.pt", "conds.pt",
                         "t3_mtl23ls_v3.safetensors", "grapheme_mtl_merged_expanded_v1.json",
                         "Cangjie5_TC.json"]),
}
REQUIRED = {
    "nano": ["ve.safetensors", "t3_nano_v1.safetensors", "s3gen_meanflow.safetensors"],
    "turbo": ["ve.safetensors", "t3_turbo_v1.safetensors", "s3gen_meanflow.safetensors"],
    "english": ["ve.safetensors", "t3_cfg.safetensors", "s3gen.safetensors", "tokenizer.json", "conds.pt"],
    "multilingual-v3": ["ve.pt", "s3gen.pt", "conds.pt", "t3_mtl23ls_v3.safetensors", "grapheme_mtl_merged_expanded_v1.json", "Cangjie5_TC.json"],
}


def main():
    from huggingface_hub import snapshot_download
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", choices=sorted(MODEL_SPECS))
    parser.add_argument("--dest", type=Path, default=Path(__file__).resolve().parent.parent / "models")
    opts = parser.parse_args()
    for model in dict.fromkeys(opts.models):
        repo, patterns = MODEL_SPECS[model]
        target = opts.dest / model
        target.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {model} from {repo} to {target}...", flush=True)
        snapshot_download(repo_id=repo, allow_patterns=patterns, local_dir=target)
        missing = [name for name in REQUIRED[model] if not (target / name).exists()]
        if missing:
            raise RuntimeError(f"Incomplete {model} download, missing: {missing}")
        if model == 'multilingual-v3':
            from chatterbox_studio.tokenizer_assets import install_pkuseg
            install_pkuseg(opts.dest/'tokenizers'/'pkuseg'/'spacy_ontonotes', Event(),
                          lambda message: print(message, flush=True))
        print(f"{model} is ready for offline packaging.", flush=True)


if __name__ == "__main__":
    main()
