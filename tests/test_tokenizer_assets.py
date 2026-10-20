"""Tokenizer setup integrity and offline constructor isolation without model downloads."""
import hashlib
import json
import sys
from threading import Event
import types
import zipfile

import pytest

from chatterbox_studio import tokenizer_assets as ta
from chatterbox_studio import model_downloads as md
from chatterbox_studio.optional_engines import EngineCancelled


def fixture_archive(tmp_path,monkeypatch,*,extra=False):
    contents={'features.msgpack':b'feature fixture','weights.npz':b'weight fixture'}
    monkeypatch.setattr(ta,'PKUSEG_FILES',{n:(len(b),hashlib.sha256(b).hexdigest()) for n,b in contents.items()})
    archive=tmp_path/'asset.zip'
    with zipfile.ZipFile(archive,'w') as packed:
        for name,data in contents.items():packed.writestr(name,data)
        if extra:packed.writestr('../outside',b'bad')
    monkeypatch.setattr(ta,'PKUSEG_SHA256',hashlib.sha256(archive.read_bytes()).hexdigest())
    return archive


def test_verified_install_and_reuse(tmp_path,monkeypatch):
    archive=fixture_archive(tmp_path,monkeypatch)
    target=tmp_path/'installed'
    assert ta.install_pkuseg(target,Event(),lambda *_:None,archive=archive)==target
    assert ta.pkuseg_ready(target)
    assert json.loads((target/'source.json').read_text())['archive_sha256']==ta.PKUSEG_SHA256
    archive.unlink()
    assert ta.install_pkuseg(target,Event(),lambda *_:None,archive=archive)==target


def test_checksum_failure_does_not_publish(tmp_path,monkeypatch):
    archive=fixture_archive(tmp_path,monkeypatch)
    archive.write_bytes(b'damaged')
    with pytest.raises(RuntimeError,match='checksum mismatch'):
        ta.install_pkuseg(tmp_path/'installed',Event(),print,archive=archive)
    assert not ta.pkuseg_ready(tmp_path/'installed')


def test_rejects_unexpected_archive_member(tmp_path,monkeypatch):
    archive=fixture_archive(tmp_path,monkeypatch,extra=True)
    with pytest.raises(RuntimeError,match='archive contents'):
        ta.install_pkuseg(tmp_path/'installed',Event(),print,archive=archive)
    assert not (tmp_path/'outside').exists()


def test_cancel_does_not_start_download(tmp_path,monkeypatch):
    event=Event();event.set()
    monkeypatch.setattr(ta.urllib.request,'urlopen',lambda *a,**kw:pytest.fail('Unexpected network access'))
    with pytest.raises(EngineCancelled):
        ta.install_pkuseg(tmp_path/'installed',event,print)


def test_local_constructor_uses_json_and_explicit_segmenter_and_restores(tmp_path,monkeypatch):
    (tmp_path/'Cangjie5_TC.json').write_text(json.dumps(['汉\tabc','字\txyz']),encoding='utf-8')
    class Original:
        def __init__(self,model_dir):
            self.word2cj={};self.cj2word={};self.segmenter=None
            self._load_cangjie_mapping(model_dir);self._init_segmenter()
    tokenizer=types.SimpleNamespace(ChineseCangjieConverter=Original)
    package=types.ModuleType('chatterbox.models.tokenizers');package.tokenizer=tokenizer
    monkeypatch.setitem(sys.modules,'chatterbox.models.tokenizers',package)
    calls=[]
    monkeypatch.setitem(sys.modules,'spacy_pkuseg',types.SimpleNamespace(pkuseg=lambda **kw:calls.append(kw) or 'segmenter'))
    monkeypatch.setattr(ta,'installed_pkuseg',lambda storage:tmp_path/'segmenter')
    with pytest.raises(ValueError,match='construction failure'):
        with ta.local_multilingual_tokenizer(tmp_path):
            converter=tokenizer.ChineseCangjieConverter(tmp_path)
            assert converter.word2cj=={'汉':'abc','字':'xyz'}
            assert converter.cj2word=={'abc':['汉'],'xyz':['字']}
            assert converter.segmenter=='segmenter'
            raise ValueError('construction failure')
    assert calls==[{'model_name':str(tmp_path/'segmenter')}]
    assert tokenizer.ChineseCangjieConverter is Original


def test_missing_asset_gives_repair_instruction(tmp_path,monkeypatch):
    monkeypatch.setattr(ta,'installed_pkuseg',lambda storage:None)
    with pytest.raises(RuntimeError,match='Model Manager'):
        with ta.local_multilingual_tokenizer(tmp_path):pass


def test_model_manager_repairs_assets_without_redownloading_weights(tmp_path,monkeypatch):
    model=md.MODELS['multilingual-v3'];folder=tmp_path/'models'/model.key
    folder.mkdir(parents=True)
    for name in model.required:(folder/name).write_bytes(b'x')
    monkeypatch.setattr(md,'bundled_models_dir',lambda:tmp_path/'no-bundle')
    monkeypatch.setattr(ta,'installed_pkuseg',lambda storage:None)
    assert md.chatterbox_status(tmp_path,model).startswith('Tokenizer download required')
    calls=[]
    monkeypatch.setattr(ta,'ensure_multilingual_assets',lambda *a,**kw:calls.append(a))
    assert md.download_chatterbox(model,tmp_path,Event(),lambda *_:None)==folder
    assert len(calls)==1
