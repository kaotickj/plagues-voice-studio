"""Enable the locally verified Vulkan runtime while preserving product settings."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1]/'plugins')]
from plagued_ai import root,app_dir,resolve_writer_settings
from writer_core.settings import default_settings
from writer_core.downloads import MODELS,RUNTIME_VERSION


def run(apply=False):
    server=root()/'runtimes/llama.cpp'/f'{RUNTIME_VERSION}-windows-vulkan'/'llama-server.exe'
    if not server.is_file():raise ValueError('Install and test the Vulkan runtime first.')
    configurations=[('dj-writer',app_dir('dj-writer')/'ai_studio.json','gemma-writer'),
                    ('promotional-writer',app_dir('voice-studio')/'plugins/promotional-writer/ai_studio.json','gemma-writer'),
                    ('interview',app_dir('voice-studio')/'plugins/promotional-writer/interview/ai_studio.json','qwen-small')]
    backup=root()/'backups'/('vulkan-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    updated=[]
    for label,path,preset in configurations:
        if path.exists():data=json.loads(path.read_text(encoding='utf-8'))
        else:
            if label=='dj-writer':raise ValueError('Open DJ Writer once to initialize its profiles before applying settings.')
            data=default_settings();data.update(model_preset=preset,model_path=str(root()/'models/text'/MODELS[preset]['filename']))
        data=resolve_writer_settings(data,path.parent)
        if not Path(data.get('model_path','')).is_file():raise ValueError('Configured model not found for '+label)
        data.update(server_path=str(server),backend='Vulkan')
        updated.append((label,path,data))
    if apply:
        benchmark=Path(__file__).resolve().parents[1]/'artifacts/vulkan-benchmark/results.json'
        results=json.loads(benchmark.read_text())
        if not all(any(r.get('preset')==preset and r.get('backend')=='Vulkan' and 'error' not in r for r in results) for preset in ('gemma-writer','qwen-small')):
            raise ValueError('Both model generation tests must pass before enabling this configuration.')
        backup.mkdir(parents=True,exist_ok=False)
        for label,path,data in updated:
            if path.exists():shutil.copy2(path,backup/(label+'.json'))
            path.parent.mkdir(parents=True,exist_ok=True)
            stage=path.with_name(path.name+'.vulkan-stage')
            stage.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8');stage.replace(path)
    print(json.dumps({'applied':apply,'backup':str(backup) if apply else None,'settings':[{'tool':label,'path':str(path),'backend':data['backend'],'model':data['model_path']} for label,path,data in updated]},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    run(parser.parse_args().apply)
