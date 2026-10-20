"""Offline CPU/DirectML inference for older shared NLP cache models."""
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from plagued_ai import root

REPOS={'bart':'facebook--bart-large-cnn','mpnet':'sentence-transformers--all-mpnet-base-v2',
       'minilm':'sentence-transformers--all-MiniLM-L6-v2'}


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True,choices=REPOS)
    args=parser.parse_args()
    out=ROOT/'artifacts/gpu-model-audit/cached-nlp'/args.model
    out.mkdir(parents=True,exist_ok=True)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    import torch
    import torch_directml
    from transformers import AutoTokenizer,AutoModel,AutoModelForSeq2SeqLM
    torch.set_num_threads(6)
    snapshots=root()/'models/huggingface/hub'/('models--'+REPOS[args.model])/'snapshots'
    snapshot=next(p for p in snapshots.iterdir() if (p/'config.json').exists())
    tokenizer=AutoTokenizer.from_pretrained(str(snapshot),local_files_only=True)
    loader=AutoModelForSeq2SeqLM if args.model=='bart' else AutoModel
    model=loader.from_pretrained(str(snapshot),local_files_only=True,torch_dtype=torch.float32,
                                 attn_implementation='eager').eval()
    report={'model':args.model,'snapshot':str(snapshot),'torch':torch.__version__,
            'gpu':torch_directml.device_name(0),'runs':[],'status':'running'}
    for backend in ('cpu','directml'):
        device=torch.device('cpu') if backend=='cpu' else torch_directml.device()
        result={'backend':backend,'status':'failed'}
        try:
            model.to(device)
            parameter_devices=sorted({str(p.device) for p in model.parameters()})
            start=time.monotonic()
            # DirectML's PyTorch 2.4 adapter needs version counters for transfers.
            with torch.no_grad():
                if args.model=='bart':
                    text=('Harbor Radio Repair is an independent workshop that repairs tabletop radios and record players. '
                          'Customers receive a written estimate before repairs begin and decide whether to approve the work. '
                          'The business wants a short radio advertisement inviting listeners to bring equipment for assessment. '
                          'It has supplied no prices, opening hours, discounts or warranty terms.')
                    encoded=tokenizer(text,return_tensors='pt',truncation=True).to(device)
                    generated=model.generate(**encoded,max_new_tokens=40,min_new_tokens=8,num_beams=1,do_sample=False)
                    result['text']=tokenizer.decode(generated[0].cpu(),skip_special_tokens=True)
                else:
                    texts=['The radio workshop repairs tabletop radios and record players.',
                           'Bring your radio to the workshop for an estimate.',
                           'The greenhouse grows tomatoes and beans.']
                    encoded=tokenizer(texts,return_tensors='pt',padding=True,truncation=True).to(device)
                    hidden=model(**encoded).last_hidden_state
                    mask=encoded['attention_mask'].unsqueeze(-1).to(hidden.dtype)
                    vectors=(hidden*mask).sum(1)/mask.sum(1).clamp(min=1)
                    vectors=torch.nn.functional.normalize(vectors,p=2,dim=1).cpu()
                    assert torch.isfinite(vectors).all()
                    result.update(texts=texts,shape=list(vectors.shape),similarity=(vectors@vectors.T).tolist())
            result.update(status='passed',parameter_devices=parameter_devices,
                          inference_seconds=round(time.monotonic()-start,3))
        except Exception as exc:result['error']=str(exc)
        report['runs'].append(result)
        (out/'result.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(result),flush=True)
    report['status']='passed' if all(r['status']=='passed' for r in report['runs']) else 'failed'
    (out/'result.json').write_text(json.dumps(report,indent=2))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
