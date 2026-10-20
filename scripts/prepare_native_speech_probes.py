"""Build immutable native-runtime layouts from existing local checkpoints."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from plagued_ai import root


def link(source,destination):
    source=Path(source).resolve(strict=True)
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        if not os.path.samefile(source,destination):raise RuntimeError('Different existing staging file: '+str(destination))
    else:os.link(source,destination)


def main():
    records={}
    for size in ('0.6B','1.7B'):
        base=root()/f'models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-{size}-Base/snapshots'
        source=next(p for p in base.iterdir() if (p/'config.json').is_file())
        destination=root()/f'models/native-audio/qwen-tts-{size}'
        for path in source.rglob('*'):
            if path.is_file():link(path,destination/path.relative_to(source))
        records['qwen-tts-'+size]={'path':str(destination),'method':'hard links; original bytes unchanged'}
    import torch
    from safetensors.torch import load_file,save_file
    english=root()/'models/chatterbox/english'
    multilingual=root()/'models/chatterbox/multilingual-v3'
    meta=json.loads((ROOT/'artifacts/gpu-model-audit/native-runtime.json').read_text())
    spec=json.loads((Path(meta['source'])/'model_specs/chatterbox.json').read_text())
    for variant in ('english','multilingual-v3'):
        destination=root()/('models/native-audio/chatterbox-'+variant)
        for folder in (english,multilingual):
            for path in folder.glob('*'):
                if path.is_file() and not (destination/path.name).exists():link(path,destination/path.name)
        changes={}
        if variant=='multilingual-v3':
            for pt,name in [('ve.pt','ve.safetensors'),('s3gen.pt','s3gen.safetensors')]:
                tensors=torch.load(multilingual/pt,map_location='cpu',weights_only=True)
                reference=load_file(str(english/name))
                identical=(tensors.keys()==reference.keys() and all(torch.equal(tensors[k],reference[k]) for k in tensors))
                changes[pt]={'identical_to_english_safetensors':identical,'tensors':len(tensors)}
                if not identical:
                    converted=destination/(Path(name).stem+'-multilingual.safetensors')
                    if not converted.exists():save_file({k:v.contiguous() for k,v in tensors.items()},str(converted))
                    changes[pt]['converted']=str(converted)
                del tensors,reference
        custom=json.loads(json.dumps(spec))
        for layout in custom['sources']:
            if layout['format']=='safetensors':
                # No v2 test is made; the loader eagerly opens an unused v2 slot.
                layout['tensors']['t3_multilingual_v2_weights']='model:t3_mtl23ls_v3.safetensors'
                for pt,name,key in [('ve.pt','ve.safetensors','voice_encoder_weights'),('s3gen.pt','s3gen.safetensors','s3gen_weights')]:
                    if changes.get(pt,{}).get('converted'):
                        layout['tensors'][key]='model:'+Path(changes[pt]['converted']).name
        target=ROOT/'artifacts/gpu-model-audit'/('spec-chatterbox-'+variant+'.json')
        target.write_text(json.dumps(custom,indent=2))
        records['chatterbox-'+variant]={'path':str(destination),'spec':str(target),'conversions':changes,
                                       'unused_v2_slot':'aliases v3; v2 is never selected or claimed tested'}
    (ROOT/'artifacts/gpu-model-audit/native-checkpoints.json').write_text(json.dumps(records,indent=2))
    print(json.dumps(records,indent=2))


if __name__=='__main__':main()
