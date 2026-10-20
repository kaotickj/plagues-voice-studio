"""Run empty-library controls using the same library-mode guard instructions."""
import json,sys,time,importlib.util
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'plugins'),str(ROOT/'plugins/dj-writer')]
from writer_core.runtime import WriterRuntime
from writer_core.settings import default_settings
from ai_writer import LocalWriter,ScriptRequest,default_settings as dj_defaults
OUT=ROOT/'artifacts/library-ablation'
manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
legacy=json.loads((Path.home()/'.goodneighbor_blues_dj/ai_studio.json').read_text(encoding='utf-8'))
base=default_settings();base.update(server_path=legacy['server_path'],model_path=str(Path.home()/'.goodneighbor_blues_dj/ai_writer/models'/manifest['model']),model_preset='gemma-writer',context_size=8192,backend='CPU',cpu_threads=6,batch_threads=12)
pkg='evaluation_control_promo';spec=importlib.util.spec_from_file_location(pkg,ROOT/'plugins/promotional-writer/__init__.py',submodule_search_locations=[str(ROOT/'plugins/promotional-writer')]);m=importlib.util.module_from_spec(spec);sys.modules[pkg]=m;spec.loader.exec_module(m)
prompts=__import__(pkg+'.prompts',fromlist=['CopyRequest'])
for product in ('promo','dj'):
 folder=OUT/(product+'-empty-control');folder.mkdir(exist_ok=True)
 print('START',product,'empty-control',flush=True)
 writer=WriterRuntime(base,folder) if product=='promo' else LocalWriter(dict(dj_defaults(),**base,wiki_lookup=False),folder)
 original=writer._request
 def request(route,payload=None,timeout=5):
  if payload is not None:
   payload=dict(payload)
   if route=='/v1/chat/completions':payload['seed']=manifest['seed']
   if route in ('/apply-template','/v1/chat/completions'):
    with (folder/'requests.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'route':route,'payload':payload},ensure_ascii=False)+'\n')
  return original(route,payload,timeout)
 writer._request=request
 try:
  if product=='promo':
   r=prompts.CopyRequest(category='Spoken advertisement',words=100,product='Harbor Radio Repair',audience='Local residents with equipment needing attention',call_to_action='Bring your equipment to the workshop for an assessment.',instructions='One conversational spoken ad. Give listeners a concrete reason to choose this business. No invented prices, address, hours or guarantees.',advertiser_context='{}')
   result=writer.generate_messages(prompts.build_messages(r),100,status=lambda s:print(product,s,flush=True))
  else:
   with patch('ai_writer.LoreLibrary.context',return_value='[]'),patch('ai_writer.CharacterLibrary.context',return_value=manifest['constant_dj_character_note']):
    result=writer.generate(ScriptRequest(**manifest['dj_request']),status=lambda s:print(product,s,flush=True))
  result.update(product=product,condition='empty-control',words=len(result['text'].split()),reference_chars=2)
  (folder/'output.txt').write_text(result['text'],encoding='utf-8')
 except Exception as exc:result=dict(product=product,condition='empty-control',error=repr(exc))
 (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('END',product,result.get('error','ok'),flush=True)
