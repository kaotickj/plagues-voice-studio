"""Real local-model library ablation. Synthetic advertiser; no private profile edits."""
import importlib.util
import json
from pathlib import Path
import sys
import time
from dataclasses import replace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'plugins'),str(ROOT/'plugins/dj-writer')]
from writer_core.runtime import WriterRuntime
from writer_core.settings import default_settings as runtime_defaults
from ai_writer import LocalWriter,ScriptRequest,default_settings as dj_defaults
from lore_library import LoreLibrary

pkg='evaluation_promo'
spec=importlib.util.spec_from_file_location(pkg,ROOT/'plugins/promotional-writer/__init__.py',submodule_search_locations=[str(ROOT/'plugins/promotional-writer')])
module=importlib.util.module_from_spec(spec);sys.modules[pkg]=module;spec.loader.exec_module(module)
prompts=__import__(pkg+'.prompts',fromlist=['CopyRequest'])
advertisers=__import__(pkg+'.advertisers',fromlist=['AdvertiserLibrary'])

OUT=ROOT/'artifacts/library-ablation';OUT.mkdir(parents=True,exist_ok=True)
legacy=json.loads((Path.home()/'.goodneighbor_blues_dj/ai_studio.json').read_text(encoding='utf-8'))
base=runtime_defaults();base.update(server_path=legacy['server_path'],model_path=str(Path.home()/'.goodneighbor_blues_dj/ai_writer/models/Gemma-The-Writer-Mighty-Sword-9B-D_AU-Q4_k_m.gguf'),model_preset='gemma-writer',backend='CPU',cpu_threads=6,batch_threads=12,context_size=8192)
SEED=731

def seeded_request(original,folder):
 def request(route,payload=None,timeout=5):
  if payload is not None:
   payload=dict(payload)
   if route=='/v1/chat/completions':payload['seed']=SEED
   if route in ('/apply-template','/v1/chat/completions'):
    with (folder/'requests.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'route':route,'payload':payload},ensure_ascii=False)+'\n')
  return original(route,payload,timeout)
 return request

profile=dict(name='Harbor Radio Repair',description='Independent workshop repairing tabletop radios and record players.',audience='Local residents who would rather repair equipment than replace it.',voice='Plainspoken, practical and welcoming. Avoid nostalgia cliches.',facts='Customers bring equipment to the workshop in person. The shop provides a written estimate before repairs.',cta='Bring your radio or record player to the workshop for an assessment.',boundaries='No supplied price, address, opening hours, turnaround or warranty terms. Do not claim free diagnosis, guaranteed results, on-site service or discounts.',answers=[{'question':'What makes the process useful?','answer':'Customers see the written estimate before deciding whether to approve repairs.','reuse':True}])
clutter=json.loads(json.dumps(profile))
clutter['answers'] += [dict(question=q,answer=a,reuse=True) for q,a in [
 ('What is the founder interested in?','The founder enjoys birdwatching and collects blue ceramic mugs.'),
 ('What happens behind the scenes?','Staff rearranged the storage shelves last month and painted a cabinet green.'),
 ('What does the team enjoy?','The team talks about old mystery novels during lunch breaks.'),
 ('What is a minor workplace tradition?','The owner names each storage cupboard after a local seabird.')]]
lib=advertisers.AdvertiserLibrary(OUT/'synthetic-profile')
contexts={'none':'','focused':lib.context(profile),'cluttered':lib.context(clutter)}
copy=prompts.CopyRequest(category='Spoken advertisement',words=100,product='Harbor Radio Repair',audience='Local residents with equipment needing attention',call_to_action='Bring your equipment to the workshop for an assessment.',instructions='One conversational spoken ad. Give listeners a concrete reason to choose this business. No invented prices, address, hours or guarantees.')

story=ScriptRequest('Tal Conroy','Stories From the Commonwealth',words=220,brief='Tell an anecdote Tal witnessed involving Piper Wright and a mistaken bundle of newspapers at the Third Rail. Keep it a small, grounded mix-up with a concrete resolution, not a quest or a moral. No violence or supernatural events.')
world=LoreLibrary(OUT/'world').context(story.brief,budget=min(3200,story.words*6))
records=LoreLibrary(OUT/'world').records()
extras=[{'title':r['title'],'text':r['text'][:500]} for r in records if r['title'] in ('The Castle','Cricket','Mutfruit (Fallout 4)','Brotherhood of Steel (Fallout 4)','The Institute','Diamond City')]
world_clutter=world+'\nADDITIONAL REFERENCE TOPICS (not requested in the brief):\n'+json.dumps(extras,ensure_ascii=False)
# Constant accepted character note: world-reference retrieval is the variable.
character='["Tal used to repair radios for caravan workers and notices practical mistakes. He dislikes being mistaken for an authority on everything."]'
manifest={'model':Path(base['model_path']).name,'seed':SEED,'hardware':'CPU','generation_threads':6,'prompt_threads':12,'context':8192,'conditions':['none','focused','cluttered'],'promo_fixture':profile,'promo_clutter_fixture':clutter,'dj_request':story.__dict__,'constant_dj_character_note':character,'world_focused':world,'world_clutter':world_clutter,'note':'One fixed-seed sample per condition; exploratory, not a universal quality benchmark. DJ clutter deliberately bypasses production retrieval cap as a stress condition.'}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
results=[]
for product in ('promo','dj'):
 for condition in ('none','focused','cluttered'):
  folder=OUT/(product+'-'+condition);folder.mkdir(exist_ok=True)
  print('START',product,condition,flush=True)
  started=time.monotonic()
  try:
   if product=='promo':
    writer=WriterRuntime(base,folder);writer._request=seeded_request(writer._request,folder)
    messages=prompts.build_messages(replace(copy,advertiser_context=contexts[condition]))
    result=writer.generate_messages(messages,copy.words,status=lambda x:print(product,condition,x,flush=True))
    result['reference_chars']=len(contexts[condition])
   else:
    settings=dj_defaults();settings.update(base);settings['wiki_lookup']=False
    writer=LocalWriter(settings,folder);writer._request=seeded_request(writer._request,folder)
    refs={'none':'','focused':world,'cluttered':world_clutter}[condition]
    with patch('ai_writer.LoreLibrary.context',return_value=refs),patch('ai_writer.CharacterLibrary.context',return_value=character):
     result=writer.generate(story,status=lambda x:print(product,condition,x,flush=True))
    result['reference_chars']=len(refs)
   result.update(product=product,condition=condition,words=len(result['text'].split()))
   (folder/'output.txt').write_text(result['text'],encoding='utf-8')
  except Exception as exc:
   result=dict(product=product,condition=condition,error=repr(exc),elapsed_seconds=round(time.monotonic()-started,2))
  (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  results.append(result)
  (OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
  print('END',product,condition,round(time.monotonic()-started,1),'seconds',result.get('error','ok'),flush=True)
print('COMPLETE',flush=True)
