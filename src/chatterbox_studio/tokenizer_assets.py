"""Explicit installation and offline use of Chatterbox's Chinese tokenizer assets."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from threading import RLock
import urllib.request
import zipfile

from plagued_ai import root as shared_root
from .paths import bundled_models_dir, canonical_data_dir

PKUSEG_URL = 'https://github.com/explosion/spacy-pkuseg/releases/download/v0.0.26/spacy_ontonotes.zip'
PKUSEG_SHA256 = 'b216e7f92de7ae285aeab8feba2faa8ea8216e5995ff6fb3d391cc8356db1bfe'
PKUSEG_FILES = {
    'features.msgpack': (22685181, 'fd4322482a7018b9bce9216173ae9d2848efe6d310b468bbb4383fb55c874a18'),
    'weights.npz': (37508754, '5ada075eb25a854f71d6e6fa4e7d55e7be0ae049255b1f8f19d05c13b1b68c9e'),
}
_TOKENIZER_LOCK = RLock()


def pkuseg_directory(storage: Path) -> Path:
    base = shared_root() if Path(storage) == canonical_data_dir() else Path(storage)
    return base/'models'/'tokenizers'/'pkuseg'/'spacy_ontonotes'


def pkuseg_ready(folder: Path) -> bool:
    try:
        return all((folder/name).is_file() and (folder/name).stat().st_size == size
                   for name, (size, _) in PKUSEG_FILES.items())
    except OSError:
        # Discovery must tolerate unavailable mounts and inaccessible legacy
        # assets. Explicit installation still reports its own write errors.
        return False


def installed_pkuseg(storage: Path) -> Path | None:
    for folder in (pkuseg_directory(storage), bundled_models_dir()/'tokenizers'/'pkuseg'/'spacy_ontonotes',
                   Path.home()/'.pkuseg'/'spacy_ontonotes'):
        if pkuseg_ready(folder):
            return folder
    return None


def install_pkuseg(target: Path, cancelled, log, *, archive: Path | None = None) -> Path:
    """User-initiated download, TLS verification, pinned archive and member hashes."""
    from .optional_engines import EngineCancelled
    def check():
        if cancelled.is_set():
            raise EngineCancelled('Tokenizer setup cancelled. Retry to finish installation.')
    check()
    if pkuseg_ready(target):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pkuseg-', dir=target.parent) as temporary:
        temporary = Path(temporary)
        if archive is None:
            log('Downloading the Multilingual Chinese segmenter (verified upstream release)…')
            archive = temporary/'download.zip'
            # urllib uses platform trust; certificate verification is never disabled.
            request = urllib.request.Request(PKUSEG_URL, headers={'User-Agent':'PlaguesVoiceStudio/1.0'})
            total = 0
            with urllib.request.urlopen(request, timeout=60) as response, archive.open('xb') as output:
                while chunk := response.read(1024*1024):
                    check()
                    total += len(chunk)
                    if total > 100*1024*1024:
                        raise RuntimeError('Unexpectedly large tokenizer archive')
                    output.write(chunk)
        with Path(archive).open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if digest != PKUSEG_SHA256:
            raise RuntimeError('Tokenizer archive checksum mismatch; installation stopped.')
        with zipfile.ZipFile(archive) as packed:
            members = packed.infolist()
            if len(members) != len(PKUSEG_FILES) or {m.filename for m in members} != set(PKUSEG_FILES):
                raise RuntimeError('Unexpected tokenizer archive contents')
            for name, (size, expected_hash) in PKUSEG_FILES.items():
                check()
                if packed.getinfo(name).file_size != size:
                    raise RuntimeError('Tokenizer file size mismatch: '+name)
                output = temporary/name
                with packed.open(name) as source, output.open('xb') as destination:
                    shutil.copyfileobj(source, destination, 1024*1024)
                with output.open('rb') as source:
                    if hashlib.file_digest(source, 'sha256').hexdigest() != expected_hash:
                        raise RuntimeError('Tokenizer file checksum mismatch: '+name)
        check()
        target.mkdir(parents=True, exist_ok=True)
        for name in PKUSEG_FILES:
            os.replace(temporary/name, target/name)
        (target/'source.json').write_text(json.dumps({'url':PKUSEG_URL, 'archive_sha256':PKUSEG_SHA256,
            'files':PKUSEG_FILES}, indent=2), encoding='utf-8')
    log('Multilingual tokenizer installed: '+str(target))
    return target


def ensure_multilingual_assets(storage: Path, cancelled, log, *, archive: Path | None = None) -> Path:
    found = installed_pkuseg(storage)
    return found if found is not None else install_pkuseg(pkuseg_directory(storage), cancelled, log, archive=archive)


@contextmanager
def local_multilingual_tokenizer(storage: Path):
    """Supply local assets to upstream's tokenizer constructor without network calls.

    The upstream converter ignores its local Cangjie JSON and starts a pkuseg
    download even for English output. Override only its constructor dependency
    while constructing this model; retain upstream tokenization/segmentation.
    """
    folder = installed_pkuseg(storage)
    if folder is None:
        raise RuntimeError('Multilingual tokenizer files are missing. In Model Manager select '
            'Chatterbox Multilingual V3 and Download selected model to repair the installation.')
    from chatterbox.models.tokenizers import tokenizer
    with _TOKENIZER_LOCK:
        original = tokenizer.ChineseCangjieConverter
        class LocalConverter(original):
            def _load_cangjie_mapping(self, model_dir=None):
                mapping = Path(model_dir)/'Cangjie5_TC.json'
                if not mapping.is_file():
                    raise RuntimeError('Multilingual Cangjie mapping is missing. Repair this model in Model Manager.')
                for entry in json.loads(mapping.read_text(encoding='utf-8')):
                    word, code = entry.split('\t')[:2]
                    self.word2cj[word] = code
                    self.cj2word.setdefault(code, []).append(word)
            def _init_segmenter(self):
                from spacy_pkuseg import pkuseg
                self.segmenter = pkuseg(model_name=str(folder))
        tokenizer.ChineseCangjieConverter = LocalConverter
        try:
            yield
        finally:
            tokenizer.ChineseCangjieConverter = original
