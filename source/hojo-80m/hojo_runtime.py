"""CPU-only, interruptible Hojo 40M runtime; upstream source stays unchanged."""
from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from onnx_model import HojoTTSLightOnnx
from text_normalize import normalize_text


class Interrupted(RuntimeError):
    pass


class Job:
    def __init__(self, timeout=60):
        self.cancelled = threading.Event()
        self.deadline = time.monotonic() + timeout
        self.options = ort.RunOptions()

    def cancel(self):
        self.cancelled.set()
        self.options.terminate = True

    def check(self):
        if self.cancelled.is_set() or time.monotonic() >= self.deadline:
            raise Interrupted('Speech cancelled or timed out')


class CheckedSession:
    def __init__(self, session, owner):
        self.session, self.owner = session, owner

    def run(self, outputs, inputs):
        job = self.owner.job
        job.check()
        result = self.session.run(outputs, inputs, run_options=job.options)
        job.check()
        return result

    def get_providers(self):
        return self.session.get_providers()


class CompleteModel(HojoTTSLightOnnx):
    def _generate_coarse_tokens(self, *args, **kwargs):
        generated, hidden = super()._generate_coarse_tokens(*args, **kwargs)
        if self.speech_end_id not in generated:
            raise RuntimeError('Speech exceeded token budget; incomplete audio discarded')
        return generated, hidden


class Runtime:
    def __init__(self, root: Path, threads=2):
        self.root, self.threads = root, threads
        self.job = None
        self.model = CompleteModel(root / 'models', provider='cpu', num_threads=threads)
        for name in ('lm', 'fine_local', 'codec_decode'):
            session = getattr(self.model, name)
            if session.get_providers() != ['CPUExecutionProvider']:
                raise RuntimeError('CPUExecutionProvider is required')
            setattr(self.model, name, CheckedSession(session, self))
        self.voices = self.model.available_voices
        # Compile/load normalization graphs once, before advertising readiness.
        normalize_text('今天是2026年，完成了50%。')
        normalize_text('Hello, 50 percent.')
        self.ffmpeg = os.environ.get('HOJO_FFMPEG', 'ffmpeg')

    def synthesize(self, text, voice, speed, job):
        # The HTTP admission gate serializes all calls (upstream uses global RNG).
        self.job = job
        try:
            job.check()
            if voice not in self.voices:
                raise ValueError('Unknown installed voice')
            normalized = normalize_text(text)
            if not normalized or len(normalized) > 800:
                raise ValueError('Normalized text must contain 1–800 characters')
            job.check()
            wav = self.model.generate(normalized, voice=voice, max_new_tokens=1600)
            job.check()
            if not len(wav) or not np.isfinite(wav).all():
                raise RuntimeError('Model returned invalid audio')
            pcm = np.rint(np.clip(wav, -1, 1) * 32767).astype('<i2').tobytes()
            if abs(speed - 1) > .0001:
                # atempo changes duration without raising/lowering the character's pitch.
                result = subprocess.run([
                    self.ffmpeg, '-hide_banner', '-loglevel', 'error', '-threads', '1',
                    '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', 'pipe:0',
                    '-af', f'atempo={speed:.3f}', '-f', 's16le', '-ar', '24000', '-ac', '1', 'pipe:1',
                ], input=pcm, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True, timeout=10)
                pcm = result.stdout
            job.check()
            if len(pcm) < 4800:
                raise RuntimeError('Model returned insufficient audio')
            return pcm
        finally:
            self.job = None
