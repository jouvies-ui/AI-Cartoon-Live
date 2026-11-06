"""Resident CPU-only Hojo 80M, with cancellable inference and reference caching."""
import os
import hashlib
import json
from pathlib import Path
import subprocess
from collections import OrderedDict

import numpy as np
from onnx_model import HojoTTSLightOnnx
from text_normalize import normalize_text
from hojo_runtime import Job, Interrupted, CheckedSession
from hojo_reference_cache import ReferenceCache


def model_directory(root):
    variant = os.environ.get('HOJO_CPU_VARIANT', 'original')
    if variant == 'original':
        return root / 'models'
    if variant != 'int8-v1':
        raise RuntimeError('Unsupported CPU optimization')
    import onnx_model
    directory = root / 'optimized' / variant
    manifest = json.loads((directory / 'optimization.json').read_text())
    source = root / 'models' / onnx_model.LM_ONNX_NAME
    graph = directory / onnx_model.LM_ONNX_NAME
    if (manifest['source_sha256'] != hashlib.sha256(source.read_bytes()).hexdigest()
            or manifest['sha256'] != hashlib.sha256(graph.read_bytes()).hexdigest()):
        raise RuntimeError('CPU optimization does not match original model')
    return directory


class Session(CheckedSession):
    def __getattr__(self, name):
        return getattr(self.session, name)


class Model(HojoTTSLightOnnx):
    def __init__(self, *args, **kwargs):
        self.reference_cache = kwargs.pop('reference_cache', None)
        super().__init__(*args, **kwargs)
        self.references = OrderedDict()

    def _cached(self, kind, path, create):
        # References are immutable and checked against SHA256 before each job.
        key = self.reference_cache.key(kind, path) if self.reference_cache else (kind, path)
        if key not in self.references:
            value = self.reference_cache.load(key, kind) if self.reference_cache else None
            if value is None:
                value = create(path)
                if self.reference_cache:
                    self.reference_cache.save(key, kind, value)
            self.references[key] = value
        self.references.move_to_end(key)
        while len(self.references) > 32:
            self.references.popitem(last=False)
        return self.references[key]

    def _encode_ref_codes(self, path):
        return self._cached('codec', path, super()._encode_ref_codes)

    def _encode_speaker(self, path):
        return self._cached('speaker', path, super()._encode_speaker)

    def _generate_coarse_tokens(self, *args, **kwargs):
        generated, hidden = super()._generate_coarse_tokens(*args, **kwargs)
        if self.speech_end_id not in generated:
            raise RuntimeError('Incomplete audio discarded')
        return generated, hidden


class Runtime:
    def __init__(self, root, threads=2):
        self.threads, self.job = threads, None
        import onnx_model
        identity = hashlib.sha256(Path(onnx_model.__file__).read_bytes() + b''.join(
            hashlib.sha256((root / 'models' / name).read_bytes()).digest()
            for name in (onnx_model.CODEC_ENCODER_NAME, onnx_model.SPEAKER_ONNX_NAME)
        )).hexdigest()
        cache = ReferenceCache(Path(os.environ.get('HOJO_CACHE_DIR', str(root / 'cache/reference-v1'))), identity)
        self.optimization = os.environ.get('HOJO_CPU_VARIANT', 'original')
        self.model = Model(model_directory(root), provider='cpu', num_threads=threads, reference_cache=cache)
        for name in ('lm', 'codec_encoder', 'decoder', 'speaker_encoder'):
            session = getattr(self.model, name)
            if session.get_providers() != ['CPUExecutionProvider']:
                raise RuntimeError('CPUExecutionProvider required')
            setattr(self.model, name, Session(session, self))
        normalize_text('今天是2026年，完成了50%。')
        normalize_text('Hello, 50 percent.')
        self.ffmpeg = os.environ.get('HOJO_FFMPEG', 'ffmpeg')

    def synthesize(self, text, preset, speed, job):
        self.job = job
        try:
            job.check()
            normalized = normalize_text(text)
            if not normalized or len(normalized) > 800:
                raise ValueError('Invalid normalized text')
            wav = self.model.generate(normalized, prompt_speech=preset['ref_audio'],
                                      prompt_text=preset['ref_text'], max_new_tokens=1600)
            job.check()
            if not len(wav) or not np.isfinite(wav).all():
                raise RuntimeError('Invalid audio')
            # Reduce an over-range utterance before PCM conversion so its peaks
            # keep their shape instead of being flattened by hard clipping.
            peak = float(np.max(np.abs(wav)))
            if peak > .98:
                wav = wav * (.98 / peak)
            pcm = np.rint(np.clip(wav, -1, 1) * 32767).astype('<i2').tobytes()
            if abs(speed - 1) > .0001:
                pcm = subprocess.run([self.ffmpeg, '-hide_banner', '-loglevel', 'error', '-threads', '1',
                    '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', 'pipe:0', '-af', f'atempo={speed:.3f}',
                    '-f', 's16le', '-ar', '24000', '-ac', '1', 'pipe:1'], input=pcm,
                    capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True, timeout=10).stdout
            job.check()
            if len(pcm) < 4800:
                raise RuntimeError('Insufficient audio')
            return pcm
        finally:
            self.job = None
