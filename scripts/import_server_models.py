"""Copy only missing model assets from the known LAN server; audit by default.

Uses existing SSH trust/identities. Never deletes or edits server model files.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from plagued_ai import root
from plagued_ai.voices import digest

SERVER='kaotickj@10.0.2.12'
NESTED=['ssh','-F','/dev/null','-i','/tmp/gnb-root-access/id_ed25519',
        '-o','UserKnownHostsFile=/tmp/gnb-root-access/known_hosts',
        '-o','HostKeyAlias=server.goodneighborblues.com','-o','IdentitiesOnly=yes',
        '-o','BatchMode=yes','root@127.0.0.1']
BASE=['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=10',SERVER]
OUT=Path(__file__).resolve().parents[1]/'artifacts/server-model-import'

INVENTORY=r'''
import hashlib,json,os,pathlib,re,subprocess
os.nice(10)
records=[]
def add(path,relative,expected=None):
 p=pathlib.Path(path)
 if not p.is_file():raise RuntimeError('Missing model asset: '+str(p))
 h=hashlib.sha256()
 with p.open('rb') as f:
  while True:
   chunk=f.read(4194304)
   if not chunk:break
   h.update(chunk)
 hashed=h.hexdigest()
 if expected and expected!=hashed:raise RuntimeError('Source blob hash mismatch: '+str(p))
 records.append({'source':str(p),'relative':relative,'size':p.stat().st_size,'sha256':hashed})
music=pathlib.Path('/var/lib/gnb-song-audio/models')
for filename in ('vae-BF16.gguf','acestep-v15-sft-Q8_0.gguf','acestep-5Hz-lm-0.6B-Q8_0.gguf','Qwen3-Embedding-0.6B-Q8_0.gguf','acestep-v15-turbo-Q8_0.gguf'):
 add(music/filename,'models/music/ace-step-1.5/'+filename)
for filename in ('kokoro-v1.0.int8.onnx','voices-v1.0.bin'):
 add(pathlib.Path('/var/lib/gnb-voice')/filename,'models/speech/kokoro/'+filename)
inspection=json.loads(subprocess.check_output(['docker','inspect','gnb-ollama']))[0]
mounts=inspection['Mounts']
model_path=next((e.split('=',1)[1] for e in inspection['Config']['Env'] if e.startswith('OLLAMA_MODELS=')),'/root/.ollama/models')
mount=next(m for m in sorted(mounts,key=lambda m:len(m['Destination']),reverse=True) if model_path==m['Destination'] or model_path.startswith(m['Destination']+'/'))
modelroot=pathlib.Path(mount['Source'])/model_path[len(mount['Destination']):].lstrip('/')
seen=set()
for family,tag in (('qwen3','0.6b'),('gemma3','1b'),('gemma3','4b')):
 relative='manifests/registry.ollama.ai/library/'+family+'/'+tag
 manifest=modelroot/relative
 add(manifest,'models/ollama/'+relative)
 data=json.loads(manifest.read_text())
 for layer in [data['config']]+data['layers']:
  sha=layer['digest']
  if not re.fullmatch(r'sha256:[0-9a-f]{64}',sha):raise RuntimeError('Unsupported blob digest')
  if sha in seen:continue
  seen.add(sha)
  filename=sha.replace(':','-')
  add(modelroot/'blobs'/filename,'models/ollama/blobs/'+filename,sha.split(':',1)[1])
print(json.dumps({'server':'10.0.2.12','models':9,'speech_voice_packs':1,'files':records}))
'''


def remote_python(script,arguments=(),stdin=None):
    remote=shlex.join(NESTED+[shlex.join(['python3','-c',script,*map(str,arguments)])])
    return subprocess.run(BASE+[remote],input=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)


def inventory():
    OUT.mkdir(parents=True,exist_ok=True)
    response=remote_python(INVENTORY)
    data=json.loads(response.stdout)
    for record in data['files']:
        relative=Path(record['relative'])
        if relative.is_absolute() or '..' in relative.parts or not str(relative).startswith('models'):
            raise ValueError('Unsafe destination in server inventory')
        if not re.fullmatch('[0-9a-f]{64}',record['sha256']) or type(record['size']) is not int or record['size']<0:
            raise ValueError('Invalid source size/hash')
    (OUT/'inventory.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    return data


def transfer(record,target):
    partial=target.with_name(target.name+'.partial')
    offset=partial.stat().st_size if partial.exists() else 0
    if offset>record['size']:raise ValueError('Oversized partial file: '+str(partial))
    script='import os,sys,shutil; p=sys.argv[1]; offset=int(sys.argv[2]); expected=int(sys.argv[3]); assert os.path.getsize(p)==expected; f=open(p,"rb"); f.seek(offset); shutil.copyfileobj(f,sys.stdout.buffer,1024*1024)'
    remote=shlex.join(NESTED+[shlex.join(['python3','-c',script,record['source'],str(offset),str(record['size'])])])
    stderr=OUT/'transfer-stderr.log'
    with stderr.open('ab') as errors, partial.open('ab') as output:
        proc=subprocess.Popen(BASE+[remote],stdout=subprocess.PIPE,stderr=errors)
        try:
            count=offset;last=time.monotonic()
            while chunk:=proc.stdout.read(4*1024*1024):
                output.write(chunk);count+=len(chunk)
                if count>record['size']:raise ValueError('Transfer exceeded expected size')
                if time.monotonic()-last>10:
                    print(f'  {count/1024**2:.0f} / {record["size"]/1024**2:.0f} MiB',flush=True);last=time.monotonic()
            if proc.wait()!=0:raise RuntimeError('SSH transfer failed; partial retained for resume. See '+str(stderr))
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
    if partial.stat().st_size!=record['size'] or digest(partial)!=record['sha256']:
        raise ValueError('Copied asset failed SHA-256 verification: '+str(partial))
    partial.replace(target)


def run(apply=False,inventory_path=None):
    data=json.loads(Path(inventory_path).read_text(encoding='utf-8')) if inventory_path else inventory()
    vault=root();files=data['files']
    by_size=defaultdict(list)
    local_roots=[vault/'models',Path.home()/'.ollama/models',Path.home()/'.lmstudio/models',Path.home()/'.cache/lm-studio/models']
    if os.environ.get('OLLAMA_MODELS'):local_roots.append(Path(os.environ['OLLAMA_MODELS']))
    for local_root in set(local_roots):
        for folder,dirs,names in os.walk(local_root,followlinks=False):
            dirs[:]=[n for n in dirs if not (Path(folder)/n).is_symlink() and not getattr(Path(folder)/n,'is_junction',lambda:False)()]
            for name in names:
                path=Path(folder)/name
                if path.is_file() and not path.is_symlink() and not name.endswith(('.partial','.lock')):
                    by_size[path.stat().st_size].append(path)
    required=0;items=[]; hashes={}
    for record in files:
        relative=Path(record['relative'])
        if relative.is_absolute() or '..' in relative.parts or not str(relative).startswith('models'):
            raise ValueError('Unsafe destination in server inventory')
        if not record['source'].startswith(('/var/lib/gnb-song-audio/models/','/var/lib/gnb-voice/','/var/lib/gnb-ollama/models/')):
            raise ValueError('Server source is outside the approved model directories')
        target=vault/relative
        if not target.resolve().is_relative_to(vault.resolve()):raise ValueError('Destination leaves shared vault')
        source=None
        for candidate in ([target] if target.is_file() else by_size[record['size']]):
            key=str(candidate)
            if key not in hashes:hashes[key]=digest(candidate)
            if hashes[key]==record['sha256']:source=candidate;break
        if target.exists() and source!=target:raise ValueError('Existing destination differs; no overwrite: '+str(target))
        action='present' if source==target else 'link' if source else 'copy'
        if action=='copy':required+=record['size']
        items.append((record,target,source,action))
    report={'server':'10.0.2.12','models':9,'voice_packs':1,'files':len(items),'bytes_to_copy':required,
            'already_present':sum(action=='present' for _,_,_,action in items),'reusable_local_files':sum(action=='link' for _,_,_,action in items)}
    print(json.dumps(report,indent=2),flush=True)
    if not apply:return
    if shutil.disk_usage(vault).free<required+5*1024**3:raise ValueError('Not enough space while retaining 5 GiB for the system.')
    completed=[]
    for record,target,source,action in items:
        print(action.upper()+' '+record['relative']+f' ({record["size"]/1024**2:.1f} MiB)',flush=True)
        target.parent.mkdir(parents=True,exist_ok=True)
        if action=='link':os.link(source,target)
        elif action=='copy':transfer(record,target)
        if target.stat().st_size!=record['size'] or digest(target)!=record['sha256']:raise ValueError('Final model verification failed')
        completed.append(dict(record,local=str(target),action=action))
        (OUT/'progress.json').write_text(json.dumps(completed,indent=2),encoding='utf-8')
    report.update(status='complete',imported_files=completed)
    (vault/'server-model-import.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('COMPLETE: all nine server models and the Kokoro voice pack are verified locally.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    parser.add_argument('--inventory',help='Reuse an already verified inventory; every copy is still verified by SHA-256.')
    arguments=parser.parse_args()
    run(arguments.apply,arguments.inventory)
