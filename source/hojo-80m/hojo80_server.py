"""Private loopback HTTP service, one resident CPU model, no GPU fallback."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(os.environ['HOJO_ROOT'])
VOICE_ROOT = Path(os.environ.get('HOJO_VOICES_DIR', str(ROOT / 'voices')))
sys.path.insert(0, str(ROOT / 'upstream' / 'Hojo-TTS-Light-80M'))

import onnx
import onnxruntime
import psutil
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from hojo80_runtime import Runtime, Job, Interrupted
from hojo_voices import load_voices

runtime = None
busy = False
stats = {'completed': 0, 'cancelled': 0, 'failed': 0, 'last_seconds': None, 'last_audio_seconds': None}
manifest = json.loads((ROOT / 'model-manifest.json').read_text())


@asynccontextmanager
async def lifespan(app):
    global runtime
    import hashlib
    for name, expected in manifest['files'].items():
        path = ROOT / 'models' / name
        if path.stat().st_size != expected['size'] or hashlib.sha256(path.read_bytes()).hexdigest() != expected['sha256']:
            raise RuntimeError(f'Model checksum mismatch: {name}')
    runtime = await asyncio.to_thread(Runtime, ROOT, int(os.environ.get('HOJO_THREADS', '2')))
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


class Speech(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=400)
    voice: str
    speed: float = Field(default=1, ge=.85, le=1.15, allow_inf_nan=False)
    voice_reference_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


def installed_voices():
    return load_voices(VOICE_ROOT, manifest['model_revision'])


@app.get('/health')
async def health():
    return {'ok': runtime is not None, 'engine': 'hojo-80m', 'device': 'cpu',
            'providers': runtime.model.lm.get_providers(), 'threads': runtime.threads,
            'onnx': onnx.__version__, 'onnxruntime': onnxruntime.__version__,
            'model_revision': manifest['model_revision'], 'sample_rate': 24000,
            'optimization': runtime.optimization, 'reference_cache': 'persistent-v1',
            'rss_mb': round(psutil.Process().memory_info().rss / 1024**2, 1),
            'busy': busy, **stats}


@app.get('/voices')
async def voices():
    return {'voices': [{'id': v, 'label': p['label'], 'reference_sha256': p['reference_sha256']} for v, p in installed_voices().items()]}


class ImportVoice(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    label: str = Field(min_length=1, max_length=48)
    transcript: str = Field(min_length=2, max_length=500)
    audio_base64: str = Field(min_length=100, max_length=14_000_000)


def import_reference(body):
    import base64
    import binascii
    import hashlib
    import io
    import shutil
    import subprocess
    import uuid
    import numpy as np
    import soundfile as sf
    try:
        raw = base64.b64decode(body.audio_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, '录音编码无效') from None
    try:
        result = subprocess.run([runtime.ffmpeg, '-hide_banner', '-loglevel', 'error',
            '-protocol_whitelist', 'pipe', '-threads', '1', '-i', 'pipe:0', '-t', '21',
            '-vn', '-ar', '24000', '-ac', '1', '-f', 'wav', 'pipe:1'],
            input=raw, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True, timeout=15)
        audio, sr = sf.read(io.BytesIO(result.stdout), dtype='float32')
    except (subprocess.SubprocessError, RuntimeError, ValueError):
        raise HTTPException(422, '无法读取录音，请使用 WAV、MP3 或 M4A') from None
    seconds = len(audio) / sr
    if not 3 <= seconds <= 20:
        raise HTTPException(422, '参考录音需为3至20秒；建议6至12秒，逐字稿需对应完整录音')
    if not np.isfinite(audio).all() or float(np.sqrt(np.mean(audio ** 2))) < .002:
        raise HTTPException(422, '录音无有效声音或音量过低')
    # Canonical PCM and transcript are immutable once published. A replacement
    # receives a new ID, so existing character templates cannot silently change.
    voice = 'hojo80_' + uuid.uuid4().hex[:16]
    root = VOICE_ROOT
    root.mkdir(mode=0o700, exist_ok=True)
    temporary, target = root / ('.import-' + voice), root / voice
    temporary.mkdir(mode=0o700)
    try:
        path = temporary / 'reference.wav'
        sf.write(path, audio, sr, subtype='PCM_16')
        data = {'id': voice, 'label': body.label, 'transcript': body.transcript,
                'audio_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'seconds': round(seconds, 3)}
        (temporary / 'voice.json').write_text(json.dumps(data, ensure_ascii=False, indent=2))
        temporary.rename(target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {'id': voice, 'label': body.label, 'seconds': data['seconds']}


@app.post('/voices/import')
async def import_voice(body: ImportVoice):
    return await asyncio.to_thread(import_reference, body)


@app.post('/synthesize')
async def synthesize(body: Speech, request: Request):
    global busy
    preset = installed_voices().get(body.voice)
    if not preset or body.voice_reference_sha256 != preset['reference_sha256']:
        raise HTTPException(422, 'Voice/model identity mismatch')
    if busy:
        raise HTTPException(429, 'CPU voice service is busy; retry after current speech', headers={'Retry-After': '1'})
    busy = True
    job = Job(timeout=60)
    started = time.monotonic()
    worker = asyncio.create_task(asyncio.to_thread(runtime.synthesize, body.text, preset, body.speed, job))
    async def monitor():
        while not worker.done():
            if await request.is_disconnected() or time.monotonic() >= job.deadline:
                job.cancel()
                return
            await asyncio.sleep(.05)
    watch = asyncio.create_task(monitor())
    try:
        pcm = await asyncio.shield(worker)
        stats.update(completed=stats['completed'] + 1,
                     last_seconds=round(time.monotonic() - started, 3),
                     last_audio_seconds=round(len(pcm) / 48000, 3))
        return Response(pcm, media_type='application/octet-stream', headers={
            'X-Audio-Format': 's16le;rate=24000;channels=1', 'X-TTS-Engine': 'hojo-80m-cpu',
            'Cache-Control': 'no-store'})
    except asyncio.CancelledError:
        job.cancel()
        stats['cancelled'] += 1
        raise
    except Exception as exc:
        cancelled = job.cancelled.is_set() or isinstance(exc, Interrupted)
        stats['cancelled' if cancelled else 'failed'] += 1
        # Text and user content never appear in service logs/errors.
        raise HTTPException(503, 'Speech cancelled or timed out' if cancelled else 'CPU speech synthesis failed') from None
    finally:
        watch.cancel()
        # Never admit a new job while the old native kernel is still running.
        try:
            await asyncio.shield(worker)
        except (Exception, asyncio.CancelledError):
            pass
        busy = False
