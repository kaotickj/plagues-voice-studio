"""Create isolated launchers in a new directory; never install or edit runtimes."""
import argparse
import json
from pathlib import Path
import shlex
import shutil


def stage(destination, index_runtime, index_repo, chatterbox_python, chatterbox_overlay,
          whisper_bin, whisper_model, ui_python, source_root,
          fast_asr_python=None, fast_asr_site=None, fast_asr_model=None):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Choose a new staging directory; existing files are never overwritten.')
    index_runtime, index_repo = Path(index_runtime).resolve(), Path(index_repo).resolve()
    whisper_bin = Path(whisper_bin).resolve()
    dependencies = dict(index_python=str(index_runtime/'python/bin/python3.11'),
        index_site=str(index_runtime/'.venv/lib/python3.11/site-packages'),
        index_repo=str(index_repo), chatterbox_python=str(Path(chatterbox_python).absolute()),
        chatterbox_overlay=str(Path(chatterbox_overlay).resolve()),
        whisper_bin=str(whisper_bin), whisper_model=str(Path(whisper_model).resolve()),
        ui_python=str(Path(ui_python).absolute()), source_root=str(Path(source_root).resolve()))
    fast = (fast_asr_python, fast_asr_site, fast_asr_model)
    if any(fast):
        if not all(fast):
            raise ValueError('Fast English ASR requires all three existing Python, site and model paths.')
        dependencies.update(fast_asr_python=str(Path(fast_asr_python).absolute()),
                            fast_asr_site=str(Path(fast_asr_site).resolve()),
                            fast_asr_model=str(Path(fast_asr_model).resolve()))
    for value in dependencies.values():
        if not Path(value).exists():
            raise ValueError('Missing local dependency: ' + value)
    for file in (whisper_bin/'whisper-cli', whisper_bin/'libwhisper.so.1', index_repo/'checkpoints/config.yaml'):
        if not file.is_file():
            raise ValueError('Missing local dependency: ' + str(file))
    if all(fast):
        for file in (Path(fast_asr_model)/'model.bin', Path(fast_asr_model)/'tokenizer.json',
                     Path(source_root)/'src/chatterbox_studio/fast_asr.py'):
            if not file.is_file():
                raise ValueError('Missing local dependency: ' + str(file))
    destination.mkdir(parents=True)
    # Frontend caches are written beside upstream source: isolate the source too.
    repo_copy = destination/'index-repo'
    shutil.copytree(index_repo, repo_copy, ignore=shutil.ignore_patterns('.git', 'checkpoints', '__pycache__', '*.pyc'))
    (repo_copy/'checkpoints').symlink_to((index_repo/'checkpoints').resolve(), target_is_directory=True)
    (destination/'dependencies.json').write_text(json.dumps(dependencies, indent=2))
    bootstrap = Path(__file__).with_name('speak_as_bootstrap.py')
    shutil.copy2(bootstrap, destination/'bootstrap.py')
    def executable(name, content):
        p = destination/name
        p.write_text(content)
        p.chmod(0o700)
        return str(p)
    launchers = {}
    for engine, python in [('index25', dependencies['index_python']), ('chatterbox', dependencies['chatterbox_python'])]:
        launchers[engine] = executable('python-'+engine, '#!/bin/sh\nexec '+shlex.quote(python)+
            ' -B '+shlex.quote(str(destination/'bootstrap.py'))+' '+engine+' "$@"\n')
    # exec preserves ownership of the ASR PID, so Cancel stops the actual engine.
    whisper = executable('whisper-local', '#!/bin/sh\nexport LD_LIBRARY_PATH='+shlex.quote(str(whisper_bin))+
        '\nexec '+shlex.quote(str(whisper_bin/'whisper-cli'))+' "$@"\n')
    config = dict(index_python=launchers['index25'], chatterbox_python=launchers['chatterbox'],
        index_repo=str(repo_copy), whisper_executable=whisper, whisper_model=dependencies['whisper_model'],
        gpu_lock='/run/lock/gnb-ai-gpu.lock')
    if all(fast):
        config['fast_asr_executable'] = executable('fast-english-asr', '#!/bin/sh\nexec '+
            shlex.quote(dependencies['fast_asr_python'])+' -B '+
            shlex.quote(str(Path(dependencies['source_root'])/'src/chatterbox_studio/fast_asr.py'))+
            ' --site '+shlex.quote(dependencies['fast_asr_site'])+' "$@"\n')
        config['fast_asr_model'] = dependencies['fast_asr_model']
    config_path = destination/'speak-as.json'
    config_path.write_text(json.dumps(config, indent=2))
    executable('preview-studio', '#!/bin/sh\nexport PVS_SPEAK_AS_CONFIG='+shlex.quote(str(config_path))+
        '\nexport PYTHONPATH='+shlex.quote(str(Path(source_root).resolve()/'src'))+
        '\nexec '+shlex.quote(dependencies['ui_python'])+' -B -m chatterbox_studio "$@"\n')
    executable('speak-as', '#!/bin/sh\nexport PVS_SPEAK_AS_CONFIG='+shlex.quote(str(config_path))+
        '\nexport PYTHONPATH='+shlex.quote(str(Path(source_root).resolve()/'src'))+
        '\nexec '+shlex.quote(dependencies['ui_python'])+' -B -m chatterbox_studio.speak_as_standalone "$@"\n')
    return config


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('destination','index-runtime','index-repo','chatterbox-python','chatterbox-overlay',
                'whisper-bin','whisper-model','ui-python','source-root'):
        p.add_argument('--'+key, required=True)
    for key in ('fast-asr-python', 'fast-asr-site', 'fast-asr-model'):
        p.add_argument('--'+key, help='Optional existing local dependency; supply all three fast ASR paths')
    print(json.dumps(stage(**vars(p.parse_args())), indent=2))
