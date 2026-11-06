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
sys.path.insert(0, str(ROOT / 'upstream' / 'Hojo-TTS-Light-40M'))

import onnx
import onnxruntime
import psutil
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from hojo_runtime import Runtime, Job, Interrupted

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


def fingerprint(voice):
    import hashlib
    identity = {'engine': 'hojo-40m', 'voice': voice,
                'model_revision': manifest['model_revision'],
                'voice_bank_sha256': manifest['files']['Hojo-TTS-Light-40M-voice.npz']['sha256']}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@app.get('/health')
async def health():
    return {'ok': runtime is not None, 'engine': 'hojo-40m', 'device': 'cpu',
            'providers': runtime.model.lm.get_providers(), 'threads': runtime.threads,
            'onnx': onnx.__version__, 'onnxruntime': onnxruntime.__version__,
            'model_revision': manifest['model_revision'], 'sample_rate': 24000,
            'rss_mb': round(psutil.Process().memory_info().rss / 1024**2, 1),
            'busy': busy, **stats}


@app.get('/voices')
async def voices():
    return {'voices': [{'id': v, 'reference_sha256': fingerprint(v)} for v in runtime.voices]}


@app.post('/synthesize')
async def synthesize(body: Speech, request: Request):
    global busy
    if body.voice not in runtime.voices or body.voice_reference_sha256 != fingerprint(body.voice):
        raise HTTPException(422, 'Voice/model identity mismatch')
    if busy:
        raise HTTPException(429, 'CPU voice service is busy; retry after current speech', headers={'Retry-After': '1'})
    busy = True
    job = Job(timeout=60)
    started = time.monotonic()
    worker = asyncio.create_task(asyncio.to_thread(runtime.synthesize, body.text, body.voice, body.speed, job))
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
            'X-Audio-Format': 's16le;rate=24000;channels=1', 'X-TTS-Engine': 'hojo-40m-cpu',
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
