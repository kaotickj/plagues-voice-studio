import argparse,json,time
from pathlib import Path
from lore_enrichment import fetch_details
from lore_library import license_link

# Concise editorial adaptations of the cited articles; no invented incidents.
from lore_enrichment import EDITOR_NOTES

def main():
 p=argparse.ArgumentParser();p.add_argument('--pack',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 entries=json.loads(a.pack.read_text(encoding='utf-8'));report=[]
 for i,e in enumerate(entries):
  try:
   facts,paragraphs=fetch_details(e)
   facts=EDITOR_NOTES.get(e['title'],facts)
   if facts:
    e['text']=' '.join(facts)[:1800];e['facts']=facts;e['curation']='Narrative sections selected for roles, relationships, motives and setting details; gameplay/appearance lists removed.'
    if e['title'] in EDITOR_NOTES:e['adaptation']='Original editorial summary of the cited article.'
   e['rights_url']=license_link({'text':e.get('license',''),'url':e.get('rights_url','')})
   e['scope']='Reference facts constrain fiction; they do not make a DJ omniscient. Keep private history, secrets and player/quest outcomes out of broadcasts unless the editor establishes them.'
   report.append({'title':e['title'],'facts':len(facts),'status':'enriched' if facts else 'needs review'})
  except (OSError,ValueError,KeyError) as exc:report.append({'title':e['title'],'status':'fetch failed','error':str(exc)})
  if (i+1)%10==0:
   a.pack.write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8');print(f'{i+1}/{len(entries)}',flush=True)
  time.sleep(.35)
 enriched_titles={r['title'] for r in report if r['status']=='enriched'}
 entries=[e for e in entries if e['title'] in enriched_titles]
 a.pack.write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
 a.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
 print('Enriched',sum(x['status']=='enriched' for x in report),'of',len(entries),flush=True)
if __name__=='__main__':main()
