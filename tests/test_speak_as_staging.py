import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('stage_speak_as',Path(__file__).parents[1]/'scripts/stage_speak_as_launchers.py')
staging=importlib.util.module_from_spec(spec)
spec.loader.exec_module(staging)


@pytest.fixture
def inputs(tmp_path):
    base=tmp_path/'local paths';base.mkdir()
    def directory(name):
        path=base/name;path.mkdir(parents=True,exist_ok=True);return path
    def file(name):
        path=base/name;path.parent.mkdir(parents=True,exist_ok=True);path.touch();return path
    runtime=directory('index-runtime')
    file('index-runtime/python/bin/python3.11')
    directory('index-runtime/.venv/lib/python3.11/site-packages')
    repo=directory('index-repo');file('index-repo/checkpoints/config.yaml')
    whisper=directory('whisper');file('whisper/whisper-cli');file('whisper/libwhisper.so.1')
    model=directory('small.en');file('small.en/model.bin');file('small.en/tokenizer.json')
    return dict(destination=tmp_path/'stage', index_runtime=runtime,index_repo=repo,
                chatterbox_python=file('chatterbox-python'),chatterbox_overlay=directory('overlay'),
                whisper_bin=whisper,whisper_model=file('ggml.bin'),ui_python=file('ui-python'),
                source_root=Path(__file__).parents[1],fast_asr_python=file('fast-python'),
                fast_asr_site=directory('fast-site'),fast_asr_model=model)


def test_optional_asr_stage_quotes_paths_and_preserves_dependencies(inputs):
    config=staging.stage(**inputs)
    target=inputs['destination'];wrapper=(target/'fast-english-asr').read_text()
    assert 'exec ' in wrapper and ' --site ' in wrapper and '"$@"' in wrapper
    assert "'"+str(inputs['fast_asr_python'])+"'" in wrapper
    assert config['fast_asr_model']==str(inputs['fast_asr_model'])
    assert json.loads((target/'speak-as.json').read_text())==config
    assert (target/'index-repo/checkpoints').resolve()==inputs['index_repo']/'checkpoints'
    assert inputs['fast_asr_model'].is_dir()
    with pytest.raises(ValueError,match='never overwritten'):staging.stage(**inputs)


def test_partial_optional_asr_fails_before_staging(inputs):
    inputs['fast_asr_site']=None
    with pytest.raises(ValueError,match='all three'):staging.stage(**inputs)
    assert not inputs['destination'].exists()


def test_missing_optional_model_fails_before_staging(inputs):
    (inputs['fast_asr_model']/'model.bin').unlink()
    with pytest.raises(ValueError,match='Missing local dependency'):staging.stage(**inputs)
    assert not inputs['destination'].exists()
