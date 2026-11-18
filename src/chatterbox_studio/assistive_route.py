"""Temporary PipeWire sink -> selectable source. No default-device changes."""
import json
import subprocess

SINK = 'plagues_voice_send'
SOURCE = 'plagues_voice_microphone'


def command():
    return ['pw-loopback', '--name', 'plagues-assistive', '--channels', '2',
            '--channel-map', '[ FL FR ]',
            '--capture-props', '{ node.name = "' + SINK + '" node.description = "Plague Voice Send" media.class = "Audio/Sink" node.virtual = true node.autoconnect = false priority.session = 0 }',
            '--playback-props', '{ node.name = "' + SOURCE + '" node.description = "Plague’s Voice Microphone" media.class = "Audio/Source" node.virtual = true node.autoconnect = false priority.session = 0 }']


def available():
    result = subprocess.run(['pw-dump'], capture_output=True, text=True, timeout=3, check=True)
    return {x.get('info', {}).get('props', {}).get('node.name') for x in json.loads(result.stdout)}


def ready():
    return {SINK, SOURCE}.issubset(available())
