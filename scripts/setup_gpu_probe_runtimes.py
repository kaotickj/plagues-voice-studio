"""Fetch pinned native Vulkan tools for isolated GPU compatibility experiments."""
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from plagued_ai import root


def fetch(url,path,expected=''):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file() and expected:
        with path.open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()==expected:return
    temporary=path.with_suffix(path.suffix+'.partial')
    digest=hashlib.sha256()
    with urllib.request.urlopen(url,timeout=120) as src,temporary.open('wb') as dst:
        while chunk:=src.read(1024*1024):
            dst.write(chunk);digest.update(chunk)
    if expected and digest.hexdigest()!=expected:raise RuntimeError('Download checksum mismatch: '+url)
    temporary.replace(path)


def extract(archive,destination,strip_root=False):
    destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        for entry in zipped.infolist():
            parts=Path(entry.filename).parts
            if strip_root:parts=parts[1:]
            if not parts:continue
            target=destination.joinpath(*parts)
            if not target.resolve().is_relative_to(destination.resolve()):raise RuntimeError('Unsafe ZIP path')
            if entry.is_dir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(zipped.read(entry))


def main():
    tag='v0.9.2-drama3-base-small'
    asset=f'audio-{tag}-bin-windows-x64-vulkan-portable.zip'
    url=f'https://github.com/0xShug0/audio.cpp/releases/download/{tag}/{asset}'
    sha='9c943d406af3543cc5005d158ed583210cd7a13371bffcd4b7f262f7a6a5ad16'
    archive=root()/'downloads/native-audio'/asset
    fetch(url,archive,sha)
    runtime=root()/'runtimes/audio.cpp'/f'{tag}-windows-vulkan'
    extract(archive,runtime)
    api='https://api.github.com/repos/0xShug0/audio.cpp/git/ref/tags/'+tag
    ref=json.load(urllib.request.urlopen(api,timeout=60))['object']
    if ref['type']=='tag':ref=json.load(urllib.request.urlopen(ref['url'],timeout=60))['object']
    commit=ref['sha']
    source_archive=ROOT/'artifacts/gpu-model-audit'/f'audio-cpp-source-{commit}.zip'
    fetch(f'https://github.com/0xShug0/audio.cpp/archive/{commit}.zip',source_archive)
    source=ROOT/'artifacts/gpu-model-audit/audio-cpp-source'
    extract(source_archive,source,strip_root=True)
    report={'runtime':str(runtime),'source':str(source),'tag':tag,'commit':commit,'url':url,'sha256':sha}
    (ROOT/'artifacts/gpu-model-audit/native-runtime.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    main()
