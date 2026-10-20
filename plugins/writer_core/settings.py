"""Product-neutral runtime configuration, stored separately for each writer."""
from pathlib import Path
import json
import os
from .downloads import MODELS, KV_CACHE_MODES
from .performance import recommended_threads
from plagued_ai import resolve_writer_settings

RUNTIME_KEYS = ('server_path', 'model_path', 'model_preset', 'backend', 'context_size',
                'cpu_threads', 'batch_threads', 'disable_repack', 'kv_cache_mode', 'auto_memory_recovery')


def default_settings():
    return dict(schema=1, server_path='', model_path='', model_preset='gemma-writer',
                backend='CPU', context_size=8192, cpu_threads=recommended_threads()[0], batch_threads=0,
                disable_repack=True, kv_cache_mode='balanced', auto_memory_recovery=True)


def validate_settings(data):
    if not isinstance(data, dict) or data.get('schema') != 1:
        raise ValueError('Unsupported writer settings; the saved file was not changed.')
    for key in ('server_path', 'model_path'):
        if not isinstance(data.get(key), str):
            raise ValueError(f'Invalid runtime setting: {key}')
    if data.get('model_preset') not in (*MODELS, 'custom') or data.get('backend') not in ('CPU', 'Vulkan'):
        raise ValueError('Choose a supported model preset and CPU or Vulkan backend.')
    for key, lower, upper in (('context_size', 1024, 32768), ('cpu_threads', 1, 32)):
        if type(data.get(key)) is not int or not lower <= data[key] <= upper:
            raise ValueError(f'{key} must be between {lower} and {upper}.')
    if type(data.get('batch_threads',0)) is not int or not 0<=data.get('batch_threads',0)<=64:
        raise ValueError('Prompt-processing threads must be Auto or between 1 and 64.')
    if data.get('kv_cache_mode') not in KV_CACHE_MODES:
        raise ValueError('Unsupported KV-cache mode.')
    for key in ('disable_repack', 'auto_memory_recovery'):
        if type(data.get(key)) is not bool:
            raise ValueError(f'{key} must be on or off.')


def load_settings(path):
    path = Path(path)
    if not path.exists():
        return default_settings()
    data = json.loads(path.read_text(encoding='utf-8'))
    validate_settings(data)
    return resolve_writer_settings(data, path.parent)


def save_settings(path, data):
    validate_settings(data)
    # Only portable runtime preferences, never another writer's profile/lore.
    clean = {'schema': 1, **{key: data.get(key,0) if key=='batch_threads' else data[key] for key in RUNTIME_KEYS}}
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    stage = path.with_suffix('.tmp')
    stage.write_text(json.dumps(clean, indent=2), encoding='utf-8')
    stage.replace(path)


def existing_runtime_settings(path):
    """Read only paths/preferences from a prior Writer install; do not copy weights."""
    path = Path(path)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding='utf-8'))
    candidate = default_settings()
    candidate.update({key: raw[key] for key in RUNTIME_KEYS if key in raw})
    validate_settings(candidate)
    if not Path(candidate['server_path']).is_file() or not Path(candidate['model_path']).is_file():
        return None
    return resolve_writer_settings(candidate, path.parent)
