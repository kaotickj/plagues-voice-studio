"""Offline CPU-only small.en adapter with the whisper-cli arguments Studio uses."""
import argparse
import os
from pathlib import Path
import socket
import sys
import time


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('-m', dest='model', type=Path, required=True)
    parser.add_argument('-f', dest='source', type=Path, required=True)
    parser.add_argument('-of', dest='output', type=Path, required=True)
    parser.add_argument('-otxt', action='store_true', required=True)
    parser.add_argument('-ng', action='store_true', required=True)
    parser.add_argument('-l', dest='language', choices=('en', 'auto'), default='en')
    parser.add_argument('-t', dest='threads', type=int, choices=range(1, 5), default=4)
    args = parser.parse_args(argv)
    for path in (args.site, args.source, args.model / 'model.bin', args.model / 'tokenizer.json'):
        if not path.exists():
            parser.error('Missing local dependency: ' + str(path))
    output = Path(str(args.output) + '.txt')
    if output.exists() or output.is_symlink():
        parser.error('Refusing to overwrite a transcript')
    os.environ.update(CUDA_VISIBLE_DEVICES='', HIP_VISIBLE_DEVICES='', ROCR_VISIBLE_DEVICES='',
                      HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex

    def offline(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise OSError('Fast English ASR is local-only; network access is disabled.')
        return original(sock, address)

    def offline_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise OSError('Fast English ASR is local-only; network access is disabled.')
        return original_ex(sock, address)

    socket.socket.connect = offline
    socket.socket.connect_ex = offline_ex
    sys.path.insert(0, str(args.site))
    try:
        from faster_whisper import WhisperModel
        started = time.monotonic()
        model = WhisperModel(str(args.model), device='cpu', compute_type='int8',
                             cpu_threads=args.threads, num_workers=1, local_files_only=True)
        segments, _ = model.transcribe(str(args.source), language='en', beam_size=5,
                                       vad_filter=False, condition_on_previous_text=False)
        text = ' '.join(segment.text.strip() for segment in segments).strip()
        if not text or len(text) > 2000:
            raise ValueError('Transcription was empty or too long')
        with output.open('x', encoding='utf-8') as handle:
            handle.write(text + '\n')
        print(f'Fast English CPU ASR: {time.monotonic() - started:.2f}s', flush=True)
    finally:
        socket.socket.connect = original
        socket.socket.connect_ex = original_ex
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
