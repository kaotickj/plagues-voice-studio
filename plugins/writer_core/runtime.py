"""Owned local llama.cpp server shared by standalone and host plugin."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import json
import os
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

from .downloads import Cancelled, KVCacheAllocationError, KV_CACHE_MODES, MODELS, context_retry_sizes, check_cancel

from .performance import thread_budgets

class WriterRuntime:
    """One owned server and one streamed completion. Closing/cancelling kills only it."""
    alias = "local-writer"
    def __init__(self, settings, data_dir):
        self.settings = deepcopy(settings)
        self.data_dir = Path(data_dir)
        self.cancelled = threading.Event()
        self._lock = threading.Lock()
        self._process = None
        self.log_path = None
        self._active_context = int(self.settings.get('context_size', 8192))

    def cancel(self):
        self.cancelled.set()
        with self._lock:
            process = self._process
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass

    def _paths(self):
        server = Path(self.settings.get('server_path', '')).expanduser()
        model = Path(self.settings.get('model_path', '')).expanduser()
        if not server.is_file():
            raise ValueError('Install or select llama-server in AI Setup first.')
        if not model.is_file() or model.suffix.lower() != '.gguf':
            raise ValueError('Download or select the writing GGUF model in AI Setup first.')
        return server.resolve(), model.resolve()

    def _start(self, server, model, context_size=None):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        self._active_context = int(context_size if context_size is not None else self.settings.get('context_size', 8192))
        key = secrets.token_hex(32)
        cpu = self.settings['backend'] == 'CPU'
        decode_threads,batch_threads=thread_budgets(self.settings)
        args = [str(server), '--model', str(model), '--host', '127.0.0.1', '--port', str(port),
                '--alias', self.alias, '--ctx-size', str(self._active_context), '--parallel', '1',
                '--threads', str(decode_threads),
                '--threads-batch', str(batch_threads),
                '--n-gpu-layers', '0' if cpu else '99', '--api-key', key, '--no-ui']
        # Avoid a several-GiB CPU_REPACK allocation on large quantized GGUFs.
        # Users can opt back in if their RAM permits and they want to benchmark speed.
        if self.settings.get('disable_repack', True):
            args.append('--no-repack')
        cache_mode = self.settings.get('kv_cache_mode', 'balanced')
        key_type, value_type = KV_CACHE_MODES[cache_mode]
        args += ['--cache-type-k', key_type, '--cache-type-v', value_type]
        if cache_mode == 'compact':
            # Quantized V requires flash attention; not supported by every runtime/backend.
            args += ['--flash-attn', 'on']
        if cpu:
            args += ['--device', 'none']
        else:
            args += ['--device', 'Vulkan0']
        logs = self.data_dir / 'ai_writer' / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        self.log_path = logs / f'write-{time.strftime("%Y%m%d-%H%M%S")}-{secrets.token_hex(3)}.log'
        env = dict(os.environ)
        # Host llama.cpp preferences must not silently override this private server.
        for name in list(env):
            if name.startswith('LLAMA_ARG_') or name in ('LLAMA_API_KEY', 'LLAMA_CACHE'):
                env.pop(name)
        env['PATH'] = str(server.parent) + os.pathsep + env.get('PATH', '')
        if os.name != 'nt':
            env['LD_LIBRARY_PATH'] = str(server.parent) + os.pathsep + env.get('LD_LIBRARY_PATH', '')
        with self._lock:
            check_cancel(self.cancelled)
            with self.log_path.open('wb') as output:
                self._process = subprocess.Popen(args, cwd=server.parent, env=env, stdin=subprocess.DEVNULL,
                                                 stdout=output, stderr=subprocess.STDOUT,
                                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self._key = key
        self._base = f'http://127.0.0.1:{port}'
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _request(self, route, payload=None, timeout=5):
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(self._base + route, data=data,
                                         headers={'Authorization': f'Bearer {self._key}', 'Content-Type': 'application/json'})
        return self._opener.open(request, timeout=timeout)

    def _wait_ready(self, status):
        started = time.monotonic()
        status(f'Loading writing model on {self.settings["backend"]}. Log: {self.log_path}')
        while time.monotonic() - started < 600:
            check_cancel(self.cancelled)
            if self._process.poll() is not None:
                log_tail = ''
                try:
                    log_tail = self.log_path.read_text(encoding='utf-8', errors='replace')[-12000:]
                except (OSError, AttributeError):
                    pass
                if 'CPU_REPACK' in log_tail and 'failed to allocate' in log_tail:
                    raise RuntimeError(
                        'llama-server ran out of allocatable memory for CPU weight repacking. '
                        'In AI Setup, turn on Disable weight repacking (--no-repack), '
                        'close other memory-heavy applications, and try again. '
                        f'Log: {self.log_path}')
                if 'failed to allocate buffer for kv cache' in log_tail.lower():
                    raise KVCacheAllocationError(
                        f'llama-server could not allocate its KV cache at {self._active_context:,} context tokens. '
                        'Try a smaller context, a lower-memory KV-cache mode, or increase Windows '
                        f'available commit memory/page file. Log: {self.log_path}')
                if 'unknown argument' in log_tail.lower() and '--no-repack' in log_tail:
                    raise RuntimeError(
                        'Your selected llama-server does not recognize --no-repack. '
                        'Install the current bundled llama.cpp runtime or turn off Disable weight repacking. '
                        f'Log: {self.log_path}')
                raise RuntimeError(f'llama-server exited while loading. See {self.log_path}')
            try:
                with self._request('/health') as response:
                    if json.load(response).get('status') != 'ok':
                        self.cancelled.wait(.4)
                        continue
                # An authenticated route ensures this is our server if the port raced.
                with self._request('/v1/models') as response:
                    result = json.load(response)
                for model in result.get('data', []):
                    if model.get('id') == self.alias:
                        trained_context = (model.get('meta') or {}).get('n_ctx_train')
                        if trained_context and self._active_context > trained_context:
                            raise ValueError(f'This model’s native context is {trained_context:,} tokens. '
                                             'Reduce Context tokens in AI Setup to that value or lower.')
                        return
            except urllib.error.HTTPError as exc:
                if exc.code not in (503, 404):
                    raise RuntimeError(f'Writing server rejected startup ({exc.code}). See {self.log_path}') from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                pass
            self.cancelled.wait(.4)
        raise TimeoutError(f'Model loading exceeded 10 minutes. See {self.log_path}')

    def _stop_server(self):
        """Clean up a failed attempt before starting another, or on exit."""
        with self._lock:
            process = self._process
        if process is not None:
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except (subprocess.TimeoutExpired, OSError):
                    try:
                        process.kill()
                    except OSError:
                        pass
                    process.wait(timeout=5)
            with self._lock:
                if self._process is process:
                    self._process = None

    def _load_with_memory_recovery(self, server, model, status):
        requested = int(self.settings.get('context_size', 8192))
        contexts = (context_retry_sizes(requested) if
                    self.settings.get('auto_memory_recovery', True) else [requested])
        previous = None
        for context in contexts:
            check_cancel(self.cancelled)
            if previous is not None:
                status(f'KV-cache memory allocation failed at {previous:,} tokens. '
                       f'Retrying with {context:,} tokens. Your saved context setting is unchanged.')
            self._start(server, model, context_size=context)
            try:
                self._wait_ready(status)
                return context
            except KVCacheAllocationError:
                self._stop_server()
                previous = context
        raise KVCacheAllocationError(
            'The KV cache could not be allocated even at the smallest context setting. '
            'Check Windows Memory > Committed versus the commit limit, enable a system-managed page file, '
            'close competing AI programs, or use a smaller model. '
            f'Last server log: {self.log_path}')

    def generate_messages(self, messages, words=120, on_text=lambda text: None, status=lambda text: None):
        """Generate one complete draft from a product's own prompt provider."""
        if not isinstance(words, int) or not 10 <= words <= 2000:
            raise ValueError('Choose a target between 10 and 2,000 words.')
        if not messages or sum(len(message['content']) for message in messages) > 24000:
            raise ValueError('Provide a writing brief of at most 24,000 characters.')
        server, model = self._paths()
        started = time.monotonic()
        try:
            decode_threads,batch_threads=thread_budgets(self.settings)
            status(f'CPU threads: generation {decode_threads}, prompt processing {batch_threads}. One model job at a time.')
            context = self._load_with_memory_recovery(server, model, status)
            loaded_at=time.monotonic()
            check_cancel(self.cancelled)
            if MODELS.get(self.settings.get('model_preset'), {}).get('single_user'):
                messages = [{'role': 'user', 'content': '\n\n'.join(m['content'] for m in messages)}]
            with self._request('/apply-template', {'messages': messages}, timeout=30) as response:
                prompt = json.load(response)['prompt']
            with self._request('/tokenize', {'content': prompt, 'add_special': True}, timeout=30) as response:
                tokens = len(json.load(response)['tokens'])
            desired = min(7200, words * 3 + 256)
            if context - tokens - 128 < desired:
                raise ValueError('The brief and word target do not fit in the available context. Shorten them or increase context in Model setup.')
            payload = dict(model=self.alias, messages=messages, stream=True, n=1,
                           temperature=.5, top_p=.85, top_k=40, repeat_penalty=1.05,
                           max_tokens=desired, chat_template_kwargs={'enable_thinking': False},
                           reasoning_format='deepseek')
            status('Writing promotional copy…')
            pieces, finish, completed = [], None, False
            first_text_at=None
            completion_started=time.monotonic()
            with self._request('/v1/chat/completions', payload, timeout=600) as response:
                for raw in response:
                    check_cancel(self.cancelled)
                    if time.monotonic() - started > 45 * 60:
                        raise TimeoutError('Writing timed out. Shorten the requested draft.')
                    line = raw.decode('utf-8').strip()
                    if not line.startswith('data:'):
                        continue
                    data = line[5:].strip()
                    if data == '[DONE]':
                        completed = True
                        break
                    event = json.loads(data)
                    if 'error' in event:
                        raise RuntimeError(str(event['error']))
                    for choice in event.get('choices', []):
                        fragment = choice.get('delta', {}).get('content') or ''
                        if not isinstance(fragment, str):
                            raise ValueError('Unsupported writing response.')
                        if fragment:
                            if first_text_at is None:first_text_at=time.monotonic()
                            pieces.append(fragment); on_text(fragment)
                        finish = choice.get('finish_reason') or finish
            check_cancel(self.cancelled)
            if not completed or finish != 'stop':
                raise RuntimeError('The draft did not finish. Increase the word target or shorten the brief; the previous draft is preserved.')
            text = ''.join(pieces).strip()
            if not text:
                raise ValueError('The writing model returned an empty draft.')
            return dict(text=text, model=model.name, elapsed_seconds=round(time.monotonic()-started, 2),
                        log=str(self.log_path), context_tokens_used=context,
                        generation_threads=decode_threads, prompt_threads=batch_threads,
                        load_seconds=round(loaded_at-started,2),
                        first_text_seconds=round(first_text_at-completion_started,2) if first_text_at else None)
        except Exception as exc:
            if self.cancelled.is_set():
                raise Cancelled('Writing cancelled; the previous draft is preserved.') from exc
            if isinstance(exc, urllib.error.HTTPError):
                detail = exc.read(2000).decode('utf-8', errors='replace')
                raise RuntimeError(f'Writing server error {exc.code}: {detail}\nLog: {self.log_path}') from exc
            raise
        finally:
            self._stop_server()
