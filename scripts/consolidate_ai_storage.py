"""Audit shared AI storage migration; --apply relocates folders with old-path aliases."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from plagued_ai.consolidation import plan, apply

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    moves=plan()
    print(json.dumps(apply(moves) if args.apply else moves,indent=2))
