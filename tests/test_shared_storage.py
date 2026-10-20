import json
from pathlib import Path
import pytest
from plagued_ai import root, app_dir, writer_models, huggingface_home
from plagued_ai.voices import plan, apply


def make_voice(folder, identifier='voice1', content=b'voice audio', filename='ref.wav'):
    (folder/'voices').mkdir(parents=True)
    (folder/'voices'/filename).write_bytes(content)
    (folder/'voices.json').write_text(json.dumps([{'id':identifier,'name':identifier,'file':filename}]))


def test_voice_merge_preserves_legacy_ids_and_deduplicates_audio(tmp_path):
    current, old, legacy, central = [tmp_path/k for k in ('current','old','legacy','central')]
    make_voice(current); make_voice(old); make_voice(legacy, 'radio-dj', b'DJ voice', 'dj.wav')
    prepared = plan(central, [(current,''),(old,''),(legacy,'legacy:')])
    assert len(prepared['records']) == 2 and len(prepared['moves']) == 3
    # Test the move and index behavior independently of Windows link privileges.
    links = []
    result = apply(prepared, lambda source, destination: links.append((source,destination)))
    assert result['status'] == 'complete'
    assert (central/'voices/ref.wav').read_bytes() == b'voice audio'
    assert (central/'voices/dj.wav').read_bytes() == b'DJ voice'
    assert {item['id'] for item in json.loads((central/'voices.json').read_text())} == {'voice1','legacy:radio-dj'}
    assert len(list((central/'voices').iterdir())) == 2 and len(links) == 3
    assert (legacy/'voices.json').is_file()


def test_voice_conflicts_fail_before_moving_anything(tmp_path):
    a,b = tmp_path/'a',tmp_path/'b'
    make_voice(a);make_voice(b, content=b'different reference')
    with pytest.raises(ValueError, match='Different voice contents'):
        plan(tmp_path/'central', [(a,''),(b,'')])
    assert (a/'voices/ref.wav').exists() and (b/'voices/ref.wav').exists()
    assert not (tmp_path/'central').exists()


def test_missing_voice_and_path_escape_are_not_silently_ignored(tmp_path):
    make_voice(tmp_path/'a')
    (tmp_path/'a/voices/ref.wav').unlink()
    with pytest.raises(ValueError,match='Missing voice'):plan(tmp_path/'central',[(tmp_path/'a','')])
    (tmp_path/'a/voices.json').write_text('[{"id":"x","name":"x","file":"../x.wav"}]')
    with pytest.raises(ValueError,match='escapes'):plan(tmp_path/'central',[(tmp_path/'a','')])


def test_shared_paths_and_custom_homes_are_distinct(monkeypatch,tmp_path):
    monkeypatch.setenv('PLAGUED_AI_HOME',str(tmp_path/'shared'))
    assert app_dir('dj-writer') == root()/'apps/dj-writer'
    assert writer_models(app_dir('voice-studio')/'plugins/promotional-writer') == root()/'models/text'
    assert writer_models(tmp_path/'test-app') == tmp_path/'test-app/ai_writer/models'
    monkeypatch.setenv('HF_HOME',str(tmp_path/'old-cache')); (tmp_path/'old-cache').mkdir()
    assert huggingface_home() == tmp_path/'old-cache'
    (root()/'models/huggingface').mkdir(parents=True)
    assert huggingface_home() == root()/'models/huggingface'


def test_folder_relocation_rolls_back_when_link_creation_fails(tmp_path):
    from plagued_ai.consolidation import plan as folder_plan, apply as move_folders
    source,target=tmp_path/'old',tmp_path/'shared/models/test'
    source.mkdir(); (source/'model.bin').write_bytes(b'keep this')
    def failed_link(*args):raise OSError('link creation failed')
    with pytest.raises(OSError,match='link creation'):
        move_folders(folder_plan([(source,target)]),tmp_path/'shared',failed_link)
    assert (source/'model.bin').read_bytes()==b'keep this' and not target.exists()


def test_model_deduplication_keeps_filenames_and_distinct_models(tmp_path):
    from plagued_ai.deduplication import plan as duplicates, apply as deduplicate
    models=tmp_path/'models'; models.mkdir()
    (models/'a.bin').write_bytes(b'model one')
    (models/'b.bin').write_bytes(b'model one')
    (models/'c.bin').write_bytes(b'model two')
    moves=duplicates(models,minimum_size=1)
    result=deduplicate(moves,models)
    assert result['bytes_reclaimed']==9 and result['files_linked']==1
    assert (models/'a.bin').samefile(models/'b.bin')
    assert not (models/'a.bin').samefile(models/'c.bin')
    assert duplicates(models,minimum_size=1)==[]


def test_shared_voice_library_resolves_preserved_legacy_ids(monkeypatch,tmp_path):
    from chatterbox_studio.pvs_library import CompatibleVoiceLibrary
    monkeypatch.setenv('PLAGUED_AI_HOME',str(tmp_path/'shared'))
    make_voice(root(),identifier='legacy:dj')
    library=CompatibleVoiceLibrary(app_dir('voice-studio'))
    assert len(library.list_voices())==1
    assert Path(library.resolve('legacy:dj')).read_bytes()==b'voice audio'
    assert library.remove_voice('legacy:dj') and not library.list_voices()


def test_shared_downloads_fetch_once_when_two_tools_request_same_model(monkeypatch,tmp_path):
    import hashlib
    import io
    import sys
    import threading
    import time
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins'))
    from writer_core.downloads import download_verified
    calls=[]; errors=[]
    payload=b'one shared model'
    class Response(io.BytesIO):
        status=200
    def request(*args,**kwargs):
        calls.append(1);time.sleep(.1);return Response(payload)
    monkeypatch.setattr('writer_core.downloads.urllib.request.urlopen',request)
    def run():
        try:
            download_verified('https://example.invalid/model',tmp_path/'model.gguf',len(payload),hashlib.sha256(payload).hexdigest(),threading.Event(),lambda *args:None)
        except Exception as exc:errors.append(exc)
    threads=[threading.Thread(target=run) for _ in range(2)]
    for thread in threads:thread.start()
    for thread in threads:thread.join(5)
    assert not any(thread.is_alive() for thread in threads)
    assert not errors and len(calls)==1
    assert (tmp_path/'model.gguf').read_bytes()==payload


def test_dj_state_migration_preserves_character_library_without_copying_models(monkeypatch,tmp_path):
    from plagued_ai import dj_data_dir
    monkeypatch.setenv('PLAGUED_AI_HOME',str(tmp_path/'shared'))
    monkeypatch.delenv('GOODNEIGHBOR_DJ_HOME',raising=False)
    monkeypatch.setattr(Path,'home',classmethod(lambda cls:tmp_path))
    legacy=tmp_path/'.goodneighbor_blues_dj'
    (legacy/'ai_writer/models').mkdir(parents=True)
    (legacy/'ai_writer/models/large.gguf').write_bytes(b'weights')
    (legacy/'ai_writer/dj_characters.json').write_text('{"Tal":"keep personality"}')
    (legacy/'history.json').write_text('["keep history"]')
    destination=dj_data_dir()
    assert (destination/'ai_writer/dj_characters.json').read_text()=='{"Tal":"keep personality"}'
    assert (destination/'history.json').read_text()=='["keep history"]'
    assert not (destination/'ai_writer/models').exists()
    assert (legacy/'ai_writer/models/large.gguf').read_bytes()==b'weights'


def test_existing_shared_runtime_is_reused_without_archive_or_network(monkeypatch,tmp_path):
    import sys,threading
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins'))
    from writer_core.downloads import install_runtime,RUNTIME_VERSION
    monkeypatch.setenv('PLAGUED_AI_HOME',str(tmp_path/'shared'))
    executable=root()/'runtimes/llama.cpp'/f'{RUNTIME_VERSION}-windows-cpu'/'llama-server.exe'
    executable.parent.mkdir(parents=True);executable.write_bytes(b'runtime')
    def unexpected_download(*args,**kwargs):raise AssertionError('A reusable runtime must not trigger download')
    monkeypatch.setattr('writer_core.downloads.download_verified',unexpected_download)
    assert Path(install_runtime(app_dir('dj-writer'),'windows-cpu',threading.Event(),lambda *args:None))==executable


def test_vulkan_capture_layer_filter_is_scoped_to_child_and_preserves_user_filters(monkeypatch,tmp_path):
    import os,sys
    from unittest.mock import patch
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins'))
    from writer_core.runtime import WriterRuntime
    from writer_core.settings import default_settings
    monkeypatch.setenv('VK_LOADER_LAYERS_DISABLE','user-custom-layer')
    settings=dict(default_settings(),backend='Vulkan')
    runtime=WriterRuntime(settings,tmp_path)
    with patch('writer_core.runtime.subprocess.Popen') as start:
        runtime._start(tmp_path/'llama-server.exe',tmp_path/'writer.gguf')
    child=start.call_args.kwargs['env']
    if os.name=='nt':assert child['VK_LOADER_LAYERS_DISABLE']=='user-custom-layer,VK_LAYER_RENDERDOC_Capture'
    assert os.environ['VK_LOADER_LAYERS_DISABLE']=='user-custom-layer'
    settings['backend']='CPU';runtime=WriterRuntime(settings,tmp_path)
    with patch('writer_core.runtime.subprocess.Popen') as start:
        runtime._start(tmp_path/'llama-server.exe',tmp_path/'writer.gguf')
    assert start.call_args.kwargs['env']['VK_LOADER_LAYERS_DISABLE']=='user-custom-layer'
