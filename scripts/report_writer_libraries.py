"""Assemble the saved, unedited local-model outputs and run protocol."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/library-ablation'
m=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
rows=[]
for path in OUT.glob('*/result.json'):
 row=json.loads(path.read_text(encoding='utf-8'));row['artifact_folder']=path.parent.name;rows.append(row)
order={'none':0,'empty-control':1,'focused':2,'cluttered':3}
rows.sort(key=lambda r:(r['product'],order.get(r['condition'],9)))
text=['# Real-generation library comparison - October 19, 2026','',
'Exploratory fixed-seed comparisons using the actual local writer pipelines. All outputs below are unedited. No model weights were trained or changed. The advertiser is a synthetic test business, not a claim about a real company.','',
f'Completed cases: {len(rows)} of 8 planned (including instruction-matched controls).','',
'## Protocol','',
f"- Model: {m['model']}; CPU, 6 generation threads / 12 prompt threads; 8,192-token context; seed {m['seed']} on every generation call.",
'- Promo target: 100 words. DJ target: 220 words, including the real story-planning stage. Each model server is stopped before the next case. No internet lookup during inference.',
'- none: original no-library mode. empty-control: empty reference object with the same library-mode guard instructions as focused/cluttered. This distinguishes instruction changes from supplied facts.',
'- focused: actual bounded retrieval / profile aggregation. cluttered: extra less-relevant facts. Promo uses its production 3,000-character profile cap; the DJ stress condition deliberately bypasses its three-topic cap. It is not normal app behavior.',
'- DJ base profile, Commonwealth rules and the same accepted character note remain constant in every DJ case. This test varies world references, not character identity.',
'- One fixed-seed sample per condition. Output lengths differ and external machine load is uncontrolled, so timings are observations, not a speed benchmark or a statistically reliable model ranking.','',
'## Observed timings','',
'| Writer | Condition | Reference characters | Output words | Total seconds |',
'|---|---|---:|---:|---:|']
for r in rows:text.append(f"| {r['product']} | {r['condition']} | {r.get('reference_chars','—')} | {r.get('words','—')} | {r.get('elapsed_seconds','—')} |")
text+=['','## Advertiser truth supplied to the model','', '```json',json.dumps(m['promo_fixture'],ensure_ascii=False,indent=2),'```','',
'## DJ brief','',m['dj_request']['brief'],'','Constant character note: '+m['constant_dj_character_note'],'']
for r in rows:
 text+=['## '+r['product']+' / '+r['condition'],'']
 if 'error' in r:text+=['Generation failed: '+r['error'],'']
 else:text +=[r['text'],'']
 if r.get('story_plan'):text+=['Story plan:','```json',json.dumps(r['story_plan'],ensure_ascii=False,indent=2),'```','']
 if r.get('warnings'):text+=['App warnings: '+ '; '.join(r['warnings']),'']
 text+=['Raw prompts/payloads: `'+r['artifact_folder']+'/requests.jsonl`.','']
if (OUT/'REVIEW.md').exists():text[4:4]=[(OUT/'REVIEW.md').read_text(encoding='utf-8')]
(OUT/'REPORT.md').write_text('\n'.join(text),encoding='utf-8')
(OUT/'all-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('Report includes',len(rows),'completed cases.')
