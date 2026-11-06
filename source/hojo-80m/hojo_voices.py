"""Immutable reference voices shared by the CPU service and bridge."""
import hashlib
import json
import re
from pathlib import Path


def reference_identity(voice, revision, audio_hash, transcript):
    identity = {'engine': 'hojo-80m', 'voice': voice, 'model_revision': revision,
                'audio_sha256': audio_hash,
                'transcript_sha256': hashlib.sha256(transcript.encode()).hexdigest()}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return identity, fingerprint


def load_voices(directory, revision):
    voices = {}
    if not directory or not revision:
        return voices
    for path in sorted(Path(directory).glob('*/voice.json')):
        try:
            data = json.loads(path.read_text())
            name = path.parent.name
            if not re.fullmatch(r'hojo80_[a-zA-Z0-9_-]{1,48}', name) or data['id'] != name:
                continue
            audio = path.parent / 'reference.wav'
            digest = hashlib.sha256(audio.read_bytes()).hexdigest()
            if digest != data['audio_sha256'] or not data['transcript'].strip():
                continue
            identity, fingerprint = reference_identity(name, revision, digest, data['transcript'])
            voices[name] = {'name': name, 'label': data['label'], 'kind': 'clone', 'engine': 'hojo',
                            'variant': '80m', 'identity': identity, 'reference_sha256': fingerprint,
                            'ref_audio': str(audio), 'ref_text': data['transcript'],
                            'language': data.get('language', 'zh'), 'gender': data.get('gender', 'u'),
                            'category': '参考录音声线 · Hojo 80M',
                            'preview_text': '你好，很高兴见到你。今天有什么想和我聊的吗？'}
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return voices
