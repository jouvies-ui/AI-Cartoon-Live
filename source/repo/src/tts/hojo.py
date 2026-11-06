"""Hojo CPU adapter: explicit routes for reference and preset voice libraries."""
from __future__ import annotations

import asyncio
import collections
import hashlib
import json
import re
import time

import httpx

MODEL_REVISION = 'c3cf21c77dc04b220aa4dabe20fc59e66a2a5485'
VOICE_BANK_SHA256 = '96cf5d470d6910fb8e0bebb5d38799d948e604746ff6ddeddb05913cab834483'


def phrases(text):
    """Bound model context without dropping characters in long read-aloud turns."""
    if len(text) <= 50:
        return [text] if text.strip() else []
    parts = re.findall(r'[^。！？!?；;\n]+[。！？!?；;\n]*|[。！？!?；;\n]+', text)
    return [part[i:i+160] for part in parts for i in range(0, len(part), 160) if part[i:i+160].strip()]


def scan_voices(config=None) -> dict:
    config = config or {}
    if config.get('hojo_variant') == '80m':
        from .hojo_voices import load_voices
        voices = load_voices(config.get('hojo_voices_dir'), config.get('hojo_model_revision'))
        if config.get('hojo_builtin_base'):
            voices.update(scan_voices())
        return voices
    voices = {}
    # IDs verified against the pinned NPZ, including en_u_01 (README lists f_08 instead).
    specs = [('zh', 'f', i) for i in (1, 2)] + [('en', 'f', i) for i in range(1, 8)] + [('en', 'm', i) for i in range(1, 6)] + [('en', 'u', 1)]
    for language, gender, index in specs:
        name = f'hojo_{language}_{gender}_{index:02d}'
        category = ('中文' if language == 'zh' else '英文') + {'f': '女声', 'm': '男声', 'u': '未标注声线'}[gender]
        identity = {'engine': 'hojo-40m', 'voice': name, 'model_revision': MODEL_REVISION,
                    'voice_bank_sha256': VOICE_BANK_SHA256}
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        voices[name] = {'name': name, 'label': f'Hojo 40M {category} {index}',
                        'kind': 'builtin', 'engine': 'hojo', 'identity': identity,
                        'variant': '40m', 'language': language, 'gender': gender, 'category': '预置声线 · ' + category,
                        'preview_text': '你好呀，很高兴见到你！我们慢慢聊，我会认真听你说。' if language == 'zh' else 'Hello! It is lovely to meet you. Tell me about your day, I am listening.',
                        'reference_sha256': fingerprint}
    return voices


class HojoTTS:
    def __init__(self, base='http://127.0.0.1:9880', timeout_sec=65, voice_config=None):
        self.cfg_base = base.rstrip('/')
        self.timeout_sec = float(timeout_sec)
        self.voice_config = voice_config or {}
        self._loop_lock = asyncio.Lock()
        self.recent_ms = collections.deque(maxlen=12)
        self.fail_streak = 0
        self.restart_count = 0
        self.last_restart_at = 0

    def active_base(self):
        return self.cfg_base

    async def synth_pcm(self, text: str, preset: dict) -> bytes:
        if not text.strip():
            return b''
        expected = scan_voices(self.voice_config).get(preset.get('name'))
        if not expected or preset.get('reference_sha256') != expected['reference_sha256']:
            raise RuntimeError('Hojo 固定声线未安装或模型版本不匹配，请在角色设置选择已安装声线。')
        base = self.cfg_base
        if self.voice_config.get('hojo_variant') == '80m' and expected.get('variant') == '40m':
            base = self.voice_config['hojo_builtin_base'].rstrip('/')
        async with self._loop_lock:
            started = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_sec, connect=3), trust_env=False) as client:
                    chunks = []
                    for phrase in phrases(text):
                        response = await client.post(base + '/synthesize', json={
                            'text': phrase, 'voice': preset['name'],
                            'voice_reference_sha256': expected['reference_sha256'],
                            'speed': (preset.get('params') or {}).get('sp', 1),
                        })
                        response.raise_for_status()
                        if response.headers.get('X-Audio-Format') != 's16le;rate=24000;channels=1':
                            raise RuntimeError('Hojo 返回了不兼容的音频格式。')
                        pcm = response.content
                        if len(pcm) < 4800 or len(pcm) % 2 or len(pcm) > 24000 * 2 * 60:
                            raise RuntimeError('Hojo 返回了无效的音频。')
                        chunks.append(pcm)
                self.fail_streak = 0
                return b''.join(chunks)
            except httpx.HTTPError as exc:
                self.fail_streak += 1
                code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
                raise RuntimeError(f'本机 CPU 语音服务暂不可用（{code}），请稍后重试。') from None
            finally:
                self.recent_ms.append(round((time.monotonic() - started) * 1000))


def create_tts(config):
    if config.get('engine', 'omnivoice') == 'hojo':
        return HojoTTS(config.get('hojo_base', 'http://127.0.0.1:9880'), config.get('hojo_timeout_sec', 65), config)
    if config.get('engine', 'omnivoice') != 'omnivoice':
        raise ValueError('Unsupported TTS engine')
    from .omnivoice import OmniVoiceTTS
    return OmniVoiceTTS(config.get('omnivoice_base', ''), config.get('omnivoice_timeout_sec', 120))
