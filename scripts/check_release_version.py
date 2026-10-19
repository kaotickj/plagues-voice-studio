"""Reject inconsistent release identities or a tag that mislabels the binary."""
import argparse
import ast
from pathlib import Path
import re
import tomllib


def check_release_identity(root, tag=None):
    root = Path(root)
    source = ast.parse((root/'src/chatterbox_studio/__init__.py').read_text(encoding='utf-8'))
    version = next(ast.literal_eval(node.value) for node in source.body
                   if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__version__' for t in node.targets))
    package = tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    installer = re.search(r'^\s*#define AppVersion "([^"]+)"', (root/'installer.iss').read_text(encoding='utf-8'), re.MULTILINE)
    metadata = ast.parse((root/'assets/version_info.txt').read_text(encoding='utf-8'))
    product = next(ast.literal_eval(node.args[1]) for node in ast.walk(metadata)
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'StringStruct'
                   and len(node.args) == 2 and ast.literal_eval(node.args[0]) == 'ProductVersion')
    if installer is None or len({version, package, installer.group(1), product}) != 1:
        raise ValueError('Source, package, installer and Windows product versions must match.')
    if tag is not None and tag != 'v' + version:
        raise ValueError(f'Expected tag v{version}, received {tag}. Refusing a mislabeled release.')
    return version


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag')
    args = parser.parse_args()
    print(check_release_identity(Path(__file__).resolve().parents[1], args.tag))
