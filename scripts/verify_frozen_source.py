"""Compare owned frozen Python code and plugin/runner files with release source."""
import argparse
import json
import marshal
from pathlib import Path
import tempfile
from types import CodeType

ROOT=Path(__file__).resolve().parents[1]


def normalized(code):
    return code.replace(co_filename='<source>',co_consts=tuple(
        normalized(value) if isinstance(value,CodeType) else value for value in code.co_consts))


def verify(exe: Path):
    from PyInstaller.archive.readers import CArchiveReader,ZlibArchiveReader
    archive=CArchiveReader(str(exe))
    compared={}
    with tempfile.TemporaryDirectory(prefix='pvs-source-check-') as temporary:
        pyz=Path(temporary)/'payload.pyz';pyz.write_bytes(archive.extract('PYZ.pyz'))
        reader=ZlibArchiveReader(str(pyz))
        for folder,prefix in [(ROOT/'src/chatterbox_studio','chatterbox_studio'),
                              (ROOT/'src/plagued_ai','plagued_ai'),
                              (ROOT/'plugins/writer_core','writer_core')]:
            for source in folder.rglob('*.py'):
                relative=source.relative_to(folder).with_suffix('')
                parts=list(relative.parts)
                if parts[-1]=='__init__':parts.pop()
                name='.'.join([prefix]+parts)
                if name not in reader.toc:continue
                compiled=compile(source.read_text(encoding='utf-8'),'<source>','exec',dont_inherit=True,optimize=0)
                compared[name]=normalized(reader.extract(name))==normalized(compiled)
    launcher=compile((ROOT/'launcher.py').read_text(encoding='utf-8'),'<source>','exec',dont_inherit=True,optimize=0)
    compared['launcher']=normalized(marshal.loads(archive.extract('launcher')))==normalized(launcher)
    internal=exe.parent/'_internal'
    compared['optional_engine_runner.py']=(internal/'optional_engine_runner.py').read_text(encoding='utf-8')==(ROOT/'optional_engine_runner.py').read_text(encoding='utf-8')
    for folder in ('promotional-writer','script-prep'):
        for source in (ROOT/'plugins'/folder).rglob('*'):
            if source.is_file() and source.suffix in ('.py','.json','.svg') and source.name!='build_plugin.py':
                relative=source.relative_to(ROOT/'plugins')
                bundled=internal/'plugins'/relative
                compared['plugins/'+str(relative)]=bundled.is_file() and bundled.read_text(encoding='utf-8')==source.read_text(encoding='utf-8')
    required={'chatterbox_studio.engine','chatterbox_studio.speech_check','chatterbox_studio.tokenizer_assets',
              'chatterbox_studio.optional_engines','writer_core.runtime','plagued_ai'}
    if not required.issubset(compared):raise RuntimeError('Missing owned modules: '+str(required-set(compared)))
    return dict(status='passed' if all(compared.values()) else 'failed',checks=compared)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    report=verify(args.exe)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(report['status'],len(report['checks']),'source/package checks')
    if report['status']!='passed':
        print([name for name,matched in report['checks'].items() if not matched]);raise SystemExit(1)
