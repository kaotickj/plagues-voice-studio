"""Package source plugin + shared runtime. No EXE, model weights or DJ shell."""
from pathlib import Path
import hashlib
import json
import zipfile


def build(destination=None):
    plugin = Path(__file__).resolve().parent
    root = plugin.parents[1]
    destination = Path(destination) if destination else plugin / 'artifacts'
    destination.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((plugin/'plugin.json').read_text(encoding='utf-8'))
    archive = destination/f'Promotional-Writer-Plugin-{manifest["version"]}.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for directory in (plugin, plugin.parent/'writer_core'):
            for source in sorted(directory.iterdir()):
                if source.is_file() and source.suffix in ('.py', '.json', '.md', '.svg', '.ps1') and source.name not in ('build_plugin.py', 'run_source.ps1'):
                    bundle.write(source, source.relative_to(root).as_posix())
        bundle.write(root/'LICENSE', 'plugins/promotional-writer/LICENSE')
        for source in sorted((root/'src'/'plagued_ai').glob('*.py')):
            bundle.write(source, 'plugins/plagued_ai/'+source.name)
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError('Plugin archive integrity check failed.')
        if any('dj-writer/' in name or name.endswith(('.exe', '.gguf')) for name in bundle.namelist()):
            raise RuntimeError('Plugin archive contains standalone code or model files.')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination/'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(f'Plugin archive: {archive}')
    return archive


if __name__ == '__main__':
    build()
