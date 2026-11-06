"""Bounded phrase delivery using backend speed and PCM level controls.

Keep the reference voice unchanged. OmniVoice's instruct vocabulary doesn't
include acting emotions; Hojo also has no native emotion input. Hojo applies speed
through pitch-preserving atempo. Don't pass invented emotion tags to either model.
"""
from copy import deepcopy
import numpy as np
from .local_performance import EXPRESSION_TONES
from .llm import clean_for_speech, split_for_tts, merge_for_tts

DELIVERIES = {
    'natural': (1.0, 1.0, 120),
    'bright': (1.07, 1.05, 90),
    'gentle': (.93, .92, 240),
    'thoughtful': (.96, .97, 260),
    'playful': (1.04, 1.03, 130),
    'firm': (.96, 1.05, 200),
    'surprised': (1.05, 1.06, 180),
}


def speech_chunks(text, first_audio=False):
    """Short replies use one inference; long host scripts may still stream."""
    if len(text) <= 50:
        return [text] if text.strip() else []
    pieces = merge_for_tts(split_for_tts(text, soft_min=14 if first_audio else 20,
                                       hard_max=44), min_chars=30,
                           first_min=12 if first_audio else 30)
    # A tiny final fragment sounds disconnected. Keep it with the preceding phrase.
    if len(pieces) > 1 and len(pieces[-1]) < 8:
        tail = pieces.pop()
        pieces[-1] += tail
    return pieces


def speech_units(segments):
    """Keep expression changes separate from synthesis boundaries."""
    annotated = [{**s, 'text': clean_for_speech(s['text']), 'segment': i}
                 for i, s in enumerate(segments)]
    annotated = [s for s in annotated if s['text'].strip()]
    if sum(len(s['text']) for s in annotated) <= 50:
        return [annotated] if annotated else []
    return [[{**s, 'text': piece,
              'gesture': s.get('gesture', 'none') if j == 0 else 'none',
              'actions': s.get('actions', []) if j == 0 else []}]
            for s in annotated for j, piece in enumerate(speech_chunks(s['text']))]


def performance_cues(unit, strength=1, auto_gestures=True):
    """Estimated semantic positions inside one audio buffer, not forced alignment.

    No silence is inserted and no audio is cut to change facial expression.
    The browser maps these proportions onto the decoded PCM duration.
    """
    total = sum(len(s['text']) for s in unit)
    cues, offset = [], 0
    for segment in unit:
        end = offset + len(segment['text'])
        cues.append({'start_ratio': offset / total, 'end_ratio': end / total,
                     'segment': segment['segment'], 'text': segment['text'],
                     'expression': segment['expression'], 'intensity': segment['intensity'] * strength,
                     'gesture': segment.get('gesture', 'none') if auto_gestures else 'none',
                     'actions': segment.get('actions', [])})
        offset = end
    return cues


def prepare_delivery(preset, segment):
    tone = segment.get('tone', EXPRESSION_TONES.get(segment['expression'], 'natural'))
    if tone not in DELIVERIES:
        raise ValueError('Unsupported speech delivery')
    speed, gain, pause = DELIVERIES[tone]
    amount = min(1.0, max(0.0, float(segment.get('intensity', .65))))
    speed = 1 + (speed - 1) * amount
    gain = 1 + (gain - 1) * amount
    selected = deepcopy(preset)
    params = selected.setdefault('params', {})
    params['sp'] = round(min(1.15, max(.85, float(params.get('sp', 1.0)) * speed)), 3)
    params['du'] = None  # A fixed duration would override the supported speed control.
    return selected, {'tone': tone, 'speed': params['sp'], 'gain': round(gain, 3), 'pause_ms': pause}


def shape_pcm(pcm, delivery):
    gain = delivery['gain']
    if not pcm or gain == 1:
        return pcm
    samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32)
    peak = float(np.max(np.abs(samples)))
    # Never introduce clipping or normalize a quiet recording into a shout.
    gain = min(gain, 32700 / peak) if peak else gain
    return np.rint(samples * gain).clip(-32700, 32700).astype('<i2').tobytes()
