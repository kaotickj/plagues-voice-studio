"""Repackage the existing trusted IndexTTS 2.5 checkpoints for native testing."""
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from plagued_ai import root


def main():
    meta=json.loads((ROOT/'artifacts/gpu-model-audit/native-runtime.json').read_text())
    script=Path(meta['source'])/'tools/community_models/convert_index_tts2_5.py'
    spec=importlib.util.spec_from_file_location('native_index_converter',script)
    converter=importlib.util.module_from_spec(spec); spec.loader.exec_module(converter)
    source=root()/'models/index-tts/2.5'
    output=root()/'models/native-audio/index25-staging'
    native=root()/'models/native-audio/index25'
    def hardlink(src,dst,label):
        src=Path(src).resolve(strict=True);dst=Path(dst)
        dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():
            if not os.path.samefile(src,dst):raise RuntimeError('Refusing to replace '+str(dst))
        else:os.link(src,dst)
        print('Reused without copying:',label,flush=True)
    converter._copy=hardlink
    sys.argv=[str(script),'--model-dir',str(source),'--output-dir',str(output),'--native-dir',str(native),
              '--campplus-checkpoint',str(source/'hf_cache/campplus_cn_common.bin')]
    return converter.main()


if __name__=='__main__':raise SystemExit(main())
