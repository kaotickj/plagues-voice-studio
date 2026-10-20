"""Exercise the imported Gemma 3 4B vision projector on the Radeon."""
import base64
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'plugins')]
from plagued_ai import root
from writer_core.runtime import WriterRuntime
from writer_core.settings import default_settings
from writer_core.downloads import RUNTIME_VERSION
import writer_core.runtime as runtime_module


def main():
    out = ROOT/'artifacts/gpu-model-audit/vision'
    out.mkdir(parents=True, exist_ok=True)
    store = root()/'models/ollama'
    manifest = next(p for p in (store/'manifests').rglob('4b') if p.parent.name == 'gemma3')
    layers = json.loads(manifest.read_text())['layers']
    paths = {}
    for kind, suffix in [('model','model'), ('projector','projector')]:
        layer = next(x for x in layers if x['mediaType'] == 'application/vnd.ollama.image.'+suffix)
        original = store/'blobs'/layer['digest'].replace(':','-')
        alias = out/(kind+'.gguf')
        if not alias.exists(): os.link(original, alias)
        paths[kind] = alias
    image = ROOT/'assets/plagues-voice-studio-icon.png'
    settings = default_settings()
    settings.update(model_path=str(paths['model']), backend='Vulkan', context_size=4096,
        cpu_threads=6, batch_threads=12, auto_memory_recovery=False,
        server_path=str(root()/'runtimes/llama.cpp'/f'{RUNTIME_VERSION}-windows-vulkan/llama-server.exe'))
    runtime = WriterRuntime(settings, out)
    report = dict(status='failed', image=str(image), model=str(paths['model']), projector=str(paths['projector']))
    started = time.monotonic()
    try:
        spawn = runtime_module.subprocess.Popen
        def with_projector(command, **kwargs):
            return spawn(list(command)+['--mmproj',str(paths['projector']),'-lv','5'], **kwargs)
        server, model = runtime._paths()
        with patch.object(runtime_module.subprocess, 'Popen', with_projector):
            runtime._start(server, model)
        runtime._wait_ready(lambda s: print(s, flush=True))
        uri = 'data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode('ascii')
        payload = dict(model=runtime.alias, stream=False, max_tokens=128, temperature=0, seed=731,
            messages=[dict(role='user', content=[dict(type='text',text='Describe the visible icon in one short sentence.'),
                dict(type='image_url',image_url=dict(url=uri))])])
        with runtime._request('/v1/chat/completions', payload, timeout=300) as response:
            result = json.load(response)
        text = result['choices'][0]['message']['content']
        if not text.strip(): raise RuntimeError('Empty image description')
        report.update(status='passed', text=text, usage=result.get('usage'))
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        runtime._stop_server()
    log = Path(runtime.log_path)
    report.update(log=str(log), elapsed_seconds=round(time.monotonic()-started,3))
    report['evidence'] = [s for s in log.read_text(errors='replace').splitlines()
        if any(k in s.lower() for k in ('vulkan','image','vision','projector','clip_model'))]
    (out/'result.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='evidence'}),flush=True)
    return 0 if report['status']=='passed' else 1


if __name__=='__main__': raise SystemExit(main())
