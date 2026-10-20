"""Find model duplicates by hash; --apply replaces only identical copies with hard links."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from plagued_ai import root
from plagued_ai.deduplication import plan, apply

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args(); moves=plan()
    if args.apply:
        result=apply(moves)
        (root()/'model-deduplication.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))
    else:print(json.dumps({'duplicates':len(moves),'bytes_reclaimable':sum(m['bytes'] for m in moves),'files':moves},indent=2))
