"""Build a portable API 1 plugin archive; no runtime or models required."""
from pathlib import Path
import hashlib
import json
import zipfile


def build(destination=None):
    plugin = Path(__file__).resolve().parent
    destination = Path(destination) if destination else plugin / 'artifacts'
    destination.mkdir(parents=True, exist_ok=True)
    version = json.loads((plugin / 'plugin.json').read_text(encoding='utf-8'))['version']
    archive = destination / f'Pronunciation-Script-Prep-Plugin-{version}.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(plugin.iterdir()):
            if path.is_file() and path.suffix in ('.py', '.md', '.json') and path.name != 'build_plugin.py':
                bundle.write(path, 'plugins/script-prep/' + path.name)
        bundle.write(plugin.parents[1] / 'src/chatterbox_studio/text_preparation.py',
                     'plugins/script-prep/time_preparation.py')
        bundle.write(plugin.parents[1] / 'LICENSE', 'plugins/script-prep/LICENSE')
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip(): raise RuntimeError('Archive integrity check failed.')
    (destination / 'SHA256SUMS.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n', encoding='utf-8')
    print(archive)
    return archive


if __name__ == '__main__':
    build()
