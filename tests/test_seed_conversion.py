import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf
from chatterbox_studio.seed_conversion import REQUIRED, assets_from_manifest, validate_profile, write_pcm_output
from chatterbox_studio.warm_worker import Session


def test_fixed_profile_rejects_unvalidated_options():
    validate_profile({})
    for key,value in [('auto_f0_adjust', False),('diffusion_steps', 2),('length_adjust',1.2),('semi_tone_shift',12),('device','mps')]:
        with pytest.raises(ValueError,match='Unsupported'):
            validate_profile({key:value})


def manifest(tmp_path):
    entries=[]
    for i,(repo,names) in enumerate(REQUIRED.items()):
        root=tmp_path/str(i);root.mkdir()
        rows=[]
        for name in names:
            p=root/name;p.write_bytes(name.encode())
            rows.append(dict(name=name,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        entries.append(dict(repo=repo,files=rows))
    p=tmp_path/'manifest.json';p.write_text(json.dumps(entries));return p,entries


def test_assets_hash_check_and_preserve_snapshot_symlinks(tmp_path):
    p,entries=manifest(tmp_path)
    row=entries[0]['files'][0];snapshot=Path(row['path']);blob=tmp_path/'blob';snapshot.rename(blob);snapshot.symlink_to(blob)
    assets=assets_from_manifest(p)
    assert assets[(entries[0]['repo'],row['name'])]==snapshot
    blob.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum mismatch'):
        assets_from_manifest(p)


def test_missing_and_duplicate_assets_rejected(tmp_path):
    p,entries=manifest(tmp_path)
    p.write_text(json.dumps(entries[:-1]))
    with pytest.raises(ValueError,match='missing'):
        assets_from_manifest(p)
    p.write_text(json.dumps(entries+entries[:1]))
    with pytest.raises(ValueError,match='Duplicate'):
        assets_from_manifest(p)


def test_pcm_output_unchanged_when_not_clipping(tmp_path):
    p=tmp_path/'out.wav';raw=np.array([.125,-.25,.5],dtype=np.float32)
    result=write_pcm_output(p,raw,44100);data,sr=sf.read(p)
    assert np.array_equal(data,raw) and sr==44100
    assert result['output_gain_db']==0


def test_pcm_overrange_uses_one_gain_not_clipping(tmp_path):
    p=tmp_path/'out.wav';raw=np.array([2.,-1.,.25],dtype=np.float32)
    result=write_pcm_output(p,raw,44100);data,sr=sf.read(p)
    assert abs(data).max()<1 and result['output_gain_db']<0
    assert np.allclose(data,raw*(.999/2),atol=1/32768)


@pytest.mark.parametrize('audio,rate',[(np.zeros(3),44100),(np.array([np.nan]),44100),(np.ones(3),16000)])
def test_invalid_model_output_rejected(tmp_path,audio,rate):
    with pytest.raises(ValueError):write_pcm_output(tmp_path/'out.wav',audio,rate)


def test_seed_warm_reuse_and_request_metadata(tmp_path):
    calls=[];marker=object()
    def convert(req,model=None):
        calls.append((req,model));return marker,dict(conversion_metadata={'auto_f0_adjust':True},conversion_note='ready')
    s=Session(validator=lambda path:None)
    with patch.dict(sys.modules,{'seed_conversion':SimpleNamespace(convert=convert)}):
        req=dict(engine='seed_v1',repo='repo',cache='cache',manifest='manifest',source='a',reference='b',output_path='out',device='cpu')
        assert not s(req)['warm']
        result=s(dict(req,source='c',reference='d'))
        assert result['warm'] and result['conversion_metadata']=={'auto_f0_adjust':True}
        assert calls[1][1] is marker and calls[1][0]['reference']=='d'
        with pytest.raises(ValueError,match='configuration changed'):s(dict(req,manifest='new'))
    s.release()


def test_reference_profile_keeps_original_and_limits_ten_seconds(tmp_path):
    from chatterbox_studio.seed_conversion import prepare_reference
    source=tmp_path/'reference.wav';target=tmp_path/'prepared.wav'
    sf.write(source,np.full((44100*12,2),.125,dtype=np.float32),44100,subtype='PCM_16')
    original=source.read_bytes()
    assert prepare_reference(source,target)==10
    data,sr=sf.read(target)
    assert data.shape==(441000,) and sr==44100 and np.all(data==.125)
    assert source.read_bytes()==original


def test_silent_reference_rejected(tmp_path):
    from chatterbox_studio.seed_conversion import prepare_reference
    source=tmp_path/'reference.wav';sf.write(source,np.zeros(44100),44100)
    with pytest.raises(ValueError,match='silent'):prepare_reference(source,tmp_path/'out.wav')


@pytest.mark.parametrize('repo', ['openai/whisper-small', 'nvidia/bigvgan_v2_44khz_128band_512x'])
def test_directory_loaded_assets_cannot_point_to_unchecked_siblings(tmp_path, repo):
    p, entries = manifest(tmp_path)
    entry = next(row for row in entries if row['repo'] == repo)
    weight = next(row for row in entry['files'] if row['name'] != 'config.json')
    old = Path(weight['path'])
    other = tmp_path / ('verified-' + old.name)
    other.write_bytes(old.read_bytes())
    weight['path'] = str(other)
    p.write_text(json.dumps(entries))
    with pytest.raises(ValueError, match='share one snapshot'):
        assets_from_manifest(p)
