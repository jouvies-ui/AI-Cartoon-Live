"""Private LiveTalking renderer, using this project's LLM and OmniVoice adapter."""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import pathlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, StrictBool

from . import config, local_character as character
from . import local_character_editor as character_editor
from .local_delivery import prepare_delivery, shape_pcm, speech_units, performance_cues
from .local_performance import ACTIONS, LIVE2D_ACTIONS, SYSTEM_PROMPT, decode_performance, decode_dialogue, dialogue_prompt, limit_reply, limit_reply_segments
from .llm import LLMClient, LLMStreamError, clean_for_speech, split_for_tts, merge_for_tts
from .tts.audio import wav_bytes

router = APIRouter()
_engine = None
_sessions = {}
_connect_lock = asyncio.Lock()


def init(engine):
    global _engine
    _engine = engine


def local_conf():
    return config.load().get('local_avatar') or {}


def live2d_enabled():
    return local_conf().get('backend') == 'live2d'


def available_actions():
    return LIVE2D_ACTIONS if live2d_enabled() and character.avatar_id() == 'whale_girl_v1' else ACTIONS


def llm_conf():
    result = dict(config.load().get('llm') or {})
    profile = character.profile() if live2d_enabled() else None
    result.update(persona='', system_prompt=dialogue_prompt(profile) if profile else SYSTEM_PROMPT,
                  max_tokens=1100 if profile else 350, temperature=0.5 if profile else 0.4)
    if profile:
        result['history_turns'] = profile.memory_turns
        result['response_format'] = 'json_object'
        result['current_identity'] = character.identity_context(profile) + (
            '\n本轮仍遵守前述JSON表演格式与50字上限。历史中的长回复不代表本轮需要展开。'
            '普通问答用15—25字直接回应，一句说清就停；保留性格口吻，不主动罗列人设、爱好或职责。'
            '只有解释、安慰或明显情绪转折确实需要时才展开至35—50字。mode=say仍完整保留原文。')
    # Honor explicit fallback models using this same endpoint and key. An
    # empty list means no fallback; never inject an unrelated default model.
    result['fallback_models'] = list(result.get('fallback_models') or [])
    return result


def editor_conf():
    result = llm_conf()
    result.update(system_prompt=character_editor.EDITOR_PROMPT, temperature=0,
                  max_tokens=1000, history_turns=0)
    result.pop('current_identity', None)
    return result


def character_catalog():
    return character.voice_catalog(_engine._voices())


class VoiceImportBody(BaseModel):
    label: str = Field(min_length=1, max_length=48)
    transcript: str = Field(min_length=2, max_length=500)
    audio_base64: str = Field(min_length=100, max_length=14_000_000)


@router.post('/api/local/voices/import')
async def import_voice(body: VoiceImportBody):
    cfg = config.load().get('tts') or {}
    if cfg.get('engine') != 'hojo' or cfg.get('hojo_variant') != '80m':
        raise HTTPException(409, '当前配音引擎尚未启用参考录音声线')
    try:
        async with httpx.AsyncClient(timeout=25, trust_env=False) as client:
            response = await client.post(cfg.get('hojo_base', 'http://127.0.0.1:9880').rstrip('/') + '/voices/import',
                                         json=body.model_dump())
        if response.status_code == 422:
            detail = response.json().get('detail')
            raise HTTPException(422, detail if isinstance(detail, str) else '录音资料无效，请检查文件与逐字稿')
        response.raise_for_status()
        result = response.json()
    except httpx.HTTPError:
        raise HTTPException(502, '本机声线导入暂不可用，请稍后重试') from None
    if result.get('id') not in {v['id'] for v in character_catalog()}:
        raise HTTPException(502, '录音已保存，但声线库尚未可用，请检查本机服务配置')
    return result


def apply_character(profile):
    character.validate_voice(profile, character_catalog())
    character.save_profile(profile)
    history = character.load_memory(profile)
    for session in _sessions.values():
        if session.backend == 'live2d' and not session.audience:
            session.llm.trim_history()
            if profile.remember:
                history = list(session.llm.history)
    # Enforce a reduced window on disk immediately, so increasing it later
    # cannot resurrect conversations the user chose to stop retaining.
    character.save_memory(history, profile)
    return profile


async def interpret_character(text, profile, catalog):
    parser = LLMClient(editor_conf)
    raw = ''
    payload = {'text': text, 'current_profile': profile.model_dump(), 'voices': catalog}
    async for delta in parser.stream(json.dumps(payload, ensure_ascii=False), record=False):
        raw += delta
    return character_editor.decode_edit(raw, text, profile, catalog)


async def renderer(path, **kwargs):
    base = local_conf().get('base_url', 'http://127.0.0.1:8010')
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(base + path, **kwargs)
        response.raise_for_status()
        result = response.json()
        if result.get('code', 0) != 0:
            raise HTTPException(502, str(result.get('msg', '渲染服务请求失败')))
        return result


@dataclass
class Session:
    backend: str = 'renderer'
    audience: bool = False
    llm: LLMClient = field(default_factory=lambda: LLMClient(llm_conf))
    task: asyncio.Task | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    touched: float = field(default_factory=time.monotonic)


class SessionBody(BaseModel):
    sessionid: str = Field(min_length=1, max_length=100)


class ConnectBody(BaseModel):
    takeover: StrictBool = False


class ChatBody(SessionBody):
    text: str = Field(min_length=1, max_length=1000)
    mode: Literal['chat', 'say', 'act'] = 'chat'


class ActionBody(SessionBody):
    actions: list[str] = Field(min_length=1, max_length=4)


class OfferBody(BaseModel):
    sdp: str = Field(min_length=1, max_length=100000)
    type: Literal['offer']


def session_for(sid):
    if sid not in _sessions:
        raise HTTPException(404, '会话已结束，请重新连接')
    return _sessions[sid]


async def cancel(session):
    if session.task and not session.task.done():
        session.task.cancel()
        await asyncio.gather(session.task, return_exceptions=True)


async def close_session(sid):
    session = _sessions.pop(sid, None)
    if session:
        async with session.lock:
            await cancel(session)
            if session.backend != 'live2d':
                await renderer('/session/close', json={'sessionid': sid})


async def release_expired_sessions():
    # Connected pages renew touched with their heartbeat. Do not interrupt
    # synthesis just because one request has taken longer than the lease.
    for sid, session in list(_sessions.items()):
        if (not session.audience and time.monotonic() - session.touched > 300
                and not (session.task and not session.task.done())):
            await close_session(sid)


@router.on_event('startup')
async def start_cleanup():
    async def cleanup():
        while True:
            await asyncio.sleep(30)
            async with _connect_lock:
                with contextlib.suppress(Exception):
                    await release_expired_sessions()
    router._cleanup = asyncio.create_task(cleanup())


@router.on_event('shutdown')
async def shutdown():
    if hasattr(router, '_cleanup'):
        router._cleanup.cancel()
        await asyncio.gather(router._cleanup, return_exceptions=True)
    for sid in list(_sessions):
        with contextlib.suppress(Exception):
            await close_session(sid)


@router.get('/local')
@router.get('/local/broadcast')
async def page():
    name = 'local_live2d.html' if live2d_enabled() else 'local.html'
    return FileResponse(pathlib.Path(__file__).resolve().parent.parent / 'stage' / name,
                        headers={'Cache-Control': 'no-cache'})


@router.get('/local/settings')
async def settings_page():
    return FileResponse(pathlib.Path(__file__).resolve().parent.parent / 'stage/local_settings.html',
                        headers={'Cache-Control': 'no-cache'})


@router.get('/local-assets/{asset_path:path}')
async def local_asset(asset_path: str):
    root = (pathlib.Path(__file__).resolve().parent.parent / 'stage/live2d').resolve()
    target = (root / asset_path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(404, '素材不存在')
    return FileResponse(target, headers={'Cache-Control': 'no-cache'})


@router.post('/api/local/connect')
async def connect_live2d(body: ConnectBody | None = None):
    if not live2d_enabled():
        raise HTTPException(409, '当前使用视频连接')
    from .local_studio import runtime
    takeover = bool(body and body.takeover)
    # Same order as studio/start. An inactive preview must not block chat,
    # while a live interaction requires the explicit takeover button.
    async with runtime.control_lock:
        if (runtime.enabled or runtime.turn_id or runtime.queue or runtime.operator_queue) and not takeover:
            raise HTTPException(409, {'code': 'live_in_use',
                'message': '直播互动或口播正在使用人物。可点击“结束直播互动并在此聊天”切换。'})
        async with _connect_lock:
            await release_expired_sessions()
            private = [sid for sid, s in _sessions.items() if not s.audience]
            if private and not takeover:
                raise HTTPException(409, {'code': 'chat_in_use',
                    'message': '另一个聊天页面仍在连接。找不到原页面时，可点击“释放旧连接并在此聊天”。'})
        # Wait for the old websocket's cleanup before creating the new session.
        # Its reconnect attempts remain suspended until studio/start is clicked.
        await runtime.release_player()
        async with _connect_lock:
            for old_sid in list(_sessions):
                await close_session(old_sid)
            sid = str(uuid.uuid4())
            session = Session(backend='live2d')
            session.llm.history.extend(character.load_memory(character.profile()))
            _sessions[sid] = session
            return {'sessionid': sid, 'backend': 'live2d'}


@router.get('/api/local/character')
async def get_character():
    profile = character.profile()
    return {'profile': profile.model_dump(), 'character_id': character.character_id(),
            'revision': character.revision(), 'voices': character_catalog(),
            'remembered_turns': len(character.load_memory(profile)) // 2}


@router.get('/api/local/appearance')
async def appearance():
    return {'id': 'whale_girl_v1', 'renderer': 'live2d', 'label': '鲸鱼娘',
            'source': 'DeepSeek 社区二创形象'}


def require_idle_character():
    if any(s.task and not s.task.done() for s in _sessions.values()):
        raise HTTPException(409, '请等本次回答生成结束，或先点击打断')


@router.post('/api/local/character')
async def save_character(profile: character.CharacterProfile):
    require_idle_character()
    try:
        apply_character(profile)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return await get_character()


@router.get('/api/local/character/export')
async def export_character():
    from fastapi.responses import JSONResponse
    try:
        template = character.export_template(character.profile(), character_catalog())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return JSONResponse(template.model_dump(), headers={
        'Content-Disposition': 'attachment; filename="character-template.json"', 'Cache-Control': 'no-store'})


@router.post('/api/local/character/import')
async def import_character(template: character.CharacterTemplate):
    require_idle_character()
    try:
        character.validate_template(template, character_catalog())
        if template.avatar != character.avatar_id():
            raise ValueError('模板形象与当前实例不同，请先部署匹配形象；本次未修改角色或记忆。')
        # Import changes this instance's profile, never its storage namespace.
        apply_character(template.profile)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return await get_character()


@router.post('/api/local/memory/clear')
async def clear_character_memory():
    require_idle_character()
    character.clear_memory()
    for session in _sessions.values():
        if session.backend == 'live2d':
            session.llm.history.clear()
    return {'ok': True, 'remembered_turns': 0}


@router.get('/api/local/health')
async def health():
    if live2d_enabled():
        root = pathlib.Path(__file__).resolve().parent.parent / 'stage/live2d'
        files = ['model/c_0120.moc3', 'model/c_0120.model3.json', 'vendor/live2dcubismcore.min.js']
        ready = all((root / p).is_file() for p in files)
        return {'ok': ready, 'renderer': '本地 Live2D', 'avatar': character.avatar_id(), 'backend': 'live2d'}
    base = local_conf().get('base_url', 'http://127.0.0.1:8010')
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            result = await client.get(base + '/api/admin/sessions')
            result.raise_for_status()
        return {'ok': True, 'renderer': local_conf().get('model', 'Wav2Lip 256'), 'avatar': local_conf().get('avatar', 'wav2lip_demo')}
    except httpx.HTTPError:
        return {'ok': False, 'detail': '数字人渲染服务暂未就绪'}


@router.get('/api/local/actions')
async def action_catalog():
    return {'actions': [{'id': k, 'label': v} for k,v in available_actions().items()]}


@router.post('/api/local/action')
async def action(body: ActionBody):
    session = session_for(body.sessionid)
    allowed = available_actions()
    if any(name not in allowed for name in body.actions):
        raise HTTPException(400, '当前形象不支持这个动作')
    async with session.lock:
        if session.backend == 'live2d':
            session.touched = time.monotonic()
            return {'ok': True, 'actions': body.actions}
        result = await renderer('/local/action', json=body.model_dump())
        session.touched = time.monotonic()
    return {'ok': True, 'action': result.get('data')}


@router.post('/api/local/offer')
async def offer(body: OfferBody):
    if live2d_enabled():
        raise HTTPException(409, '当前使用Live2D连接')
    async with _connect_lock:
        if _sessions:
            raise HTTPException(409, '当前已有连接，请先在原页面断开；闲置五分钟自动释放')
        try:
            result = await renderer('/offer', json={**body.model_dump(), 'avatar': local_conf().get('avatar', 'wav2lip_demo')})
        except httpx.HTTPError as exc:
            raise HTTPException(502, '渲染服务连接失败') from exc
        sid = result.get('sessionid')
        if not sid:
            raise HTTPException(502, '渲染服务没有返回会话')
        _sessions[sid] = Session()
        return result


@router.post('/api/local/close')
async def close(body: SessionBody):
    await close_session(body.sessionid)
    return {'ok': True}


@router.post('/api/local/interrupt')
async def interrupt(body: SessionBody):
    session = session_for(body.sessionid)
    async with session.lock:
        await cancel(session)
        if session.backend != 'live2d':
            await renderer('/interrupt_talk', json=body.model_dump())
    session.touched = time.monotonic()
    return {'ok': True}


@router.post('/api/local/status')
async def status(body: SessionBody):
    session = session_for(body.sessionid)
    session.touched = time.monotonic()
    if session.backend == 'live2d':
        return {'ok': True, 'busy': bool(session.task and not session.task.done()),
                'speaking': None, 'rendering': 'browser'}
    result = await renderer('/is_speaking', json=body.model_dump())
    action_result = await renderer('/local/action', json=body.model_dump())
    return {'ok': True, 'speaking': bool(result.get('data')), 'busy': bool(session.task and not session.task.done()), 'action': action_result.get('data', {})}


@router.post('/api/local/chat')
async def chat(body: ChatBody):
    session = session_for(body.sessionid)
    if not body.text.strip():
        raise HTTPException(400, '请输入文字')
    events = asyncio.Queue()

    async def produce_dialogue():
        started = time.monotonic()
        profile = character.profile()
        session.llm.trim_history()
        control_reply = None
        if body.mode == 'chat' and not session.audience and character_editor.may_edit(body.text):
            catalog = character_catalog()
            try:
                edit = await interpret_character(body.text, profile, catalog)
            except (ValueError, TypeError):
                edit = {'intent': 'rejected', 'message': '这次没有可靠识别出可保存的角色设置，默认档案未修改。可以说“以后你叫澜澜”，或在角色设置里直接修改。'}
            if edit['intent'] == 'update':
                profile = apply_character(edit['profile'])
                control_reply = character_editor.edit_summary(profile, edit['changed'], catalog)
                await events.put({'event': 'character_updated', **await get_character(),
                                  'changed': edit['changed']})
            elif edit['intent'] == 'rejected':
                control_reply = edit['message']
            elif edit['intent'] == 'inspect':
                voice = next((v['label'] for v in catalog if v['id'] == profile.voice_template), '未安装')
                control_reply = f'我现在叫{profile.name}，默认声线是{voice}。可选声线有：' + '、'.join(v['label'] for v in catalog) + '。性格和说话习惯可以在角色设置里查看，也可以直接告诉我怎么改。'
        if control_reply is not None:
            plan = {'segments': [{'text': control_reply, 'expression': 'neutral', 'intensity': .55,
                                  'gesture': 'none', 'actions': []}], 'actions': []}
        else:
            raw = ''
            async for delta in session.llm.stream(json.dumps({'mode': body.mode, 'text': body.text}, ensure_ascii=False), record=False):
                raw += delta
            try:
                plan = decode_dialogue(raw, available_actions())
            except (ValueError, TypeError):
                if body.mode != 'say':
                    raise
                plan = {'segments': [], 'actions': []}
        segments = limit_reply_segments(plan['segments']) if body.mode == 'chat' else plan['segments']
        if body.mode == 'say' and ''.join(s['text'] for s in segments) != body.text.strip():
            # Never let emotional annotation rewrite text in verbatim reading mode.
            segments = [{'text': body.text.strip(), 'expression': 'neutral', 'intensity': .5,
                         'gesture': 'none', 'actions': []}]
        if body.mode == 'act':
            actions = plan['actions'] + [a for s in segments for a in s['actions']]
            if actions:
                await events.put({'event': 'action', 'actions': actions[:4]})
            else:
                await events.put({'event': 'text', 'delta': '这句话没有触发可用动作。可试试“微笑后点头”。'})
            await events.put({'event': 'done', 'seconds': round(time.monotonic() - started, 3)})
            return
        if not segments:
            raise ValueError('Empty dialogue')
        reply = ''.join(s['text'] for s in segments)
        await events.put({'event': 'text', 'delta': reply})
        model_seconds = round(time.monotonic() - started, 3)
        await events.put({'event': 'plan', 'character': profile.name, 'situation': plan.get('situation', 'conversation'),
                          'segments': segments, 'model_seconds': model_seconds})
        # Do not silently fall back to an unrelated global voice after rename,
        # import or migration. This profile owns its actual synthesis template.
        character.validate_voice(profile, character_catalog())
        preset = _engine._voices()[profile.voice_template]
        first_audio = True
        for unit in speech_units(segments):
            # Choose one delivery for the continuous utterance; expression cues
            # can change without launching more TTS jobs or adding silent gaps.
            lead = max(unit, key=lambda s: len(s['text']))
            delivered_preset, delivery = prepare_delivery(preset, lead)
            speech = ''.join(s['text'] for s in unit)
            pcm = await _engine.tts.synth_pcm(speech, delivered_preset)
            if not pcm:
                raise ValueError('Empty speech audio')
            pcm = shape_pcm(pcm, delivery)
            cues = performance_cues(unit, profile.expression_strength, profile.auto_gestures)
            await events.put({'event': 'audio_chunk', 'wav': base64.b64encode(wav_bytes(pcm)).decode('ascii'),
                              **{k: v for k, v in cues[0].items() if k not in ('start_ratio', 'end_ratio')},
                              'text': speech, 'performance_cues': cues, 'cue_timing': 'estimated',
                              'voice_template': profile.voice_template, 'delivery': delivery,
                              'pause_before_ms': 0})
            if first_audio:
                first_audio_seconds = round(time.monotonic() - started, 3)
                await events.put({'event': 'audio', 'seconds': first_audio_seconds,
                                  'model_seconds': model_seconds,
                                  'first_tts_seconds': round(first_audio_seconds - model_seconds, 3)})
                first_audio = False
        if body.mode == 'chat' and control_reply is None:
            # Store only conversational text, never generated control parameters.
            session.llm.history.extend([{'role': 'user', 'content': body.text}, {'role': 'assistant', 'content': reply}])
            session.llm.trim_history()
            if not session.audience:
                character.save_memory(session.llm.history, profile)
        await events.put({'event': 'done', 'seconds': round(time.monotonic() - started, 3),
                          'remembered_turns': len(session.llm.history) // 2 if profile.remember and not session.audience else 0})

    async def produce():
        started = time.monotonic()
        try:
            if session.backend == 'live2d':
                await produce_dialogue()
                return
            reply, actions, expression = '', [], 'neutral'
            if body.mode in ('chat', 'act'):
                raw = ''
                session.llm.trim_history()
                async for delta in session.llm.stream(json.dumps({'mode': body.mode, 'text': body.text}, ensure_ascii=False)):
                    raw += delta
                reply, actions, expression = decode_performance(raw, LIVE2D_ACTIONS if session.backend == 'live2d' else ACTIONS)
            else:
                reply = body.text
            if body.mode == 'chat':
                reply = limit_reply(reply)
            if reply and body.mode != 'act':
                await events.put({'event': 'text', 'delta': reply})
            if body.mode == 'act':
                if actions:
                    if session.backend != 'live2d':
                        await renderer('/local/action', json={'sessionid': body.sessionid, 'actions': actions})
                    await events.put({'event': 'action', 'actions': actions})
                else:
                    await events.put({'event': 'text', 'delta': '这句话没有触发可用动作。可试试“微笑后点头”。'})
                await events.put({'event': 'done', 'seconds': round(time.monotonic() - started, 3)})
                return
            if actions:
                await events.put({'event': 'action', 'actions': actions, 'scheduled': True})
            speech = clean_for_speech(reply)
            if not speech.strip():
                raise RuntimeError('模型未返回可朗读的文字')
            first = True
            for piece in ([speech] if len(speech) <= 50 else split_for_tts(speech, soft_min=20, hard_max=80)):
                pcm = await _engine.tts.synth_pcm(piece, _engine._voice_preset())
                if session.backend == 'live2d':
                    await events.put({'event': 'audio_chunk', 'wav': base64.b64encode(wav_bytes(pcm)).decode('ascii'),
                                      'expression': expression, 'actions': actions if first else []})
                else:
                    await renderer('/humanaudio', data={'sessionid': body.sessionid, 'actions': json.dumps(actions if first else []), 'expression': expression},
                                   files={'file': ('speech.wav', wav_bytes(pcm), 'audio/wav')})
                if first:
                    await events.put({'event': 'audio', 'seconds': round(time.monotonic() - started, 3)})
                    first = False
            await events.put({'event': 'done', 'seconds': round(time.monotonic() - started, 3)})
        except asyncio.CancelledError:
            await events.put({'event': 'interrupted'})
            raise
        except LLMStreamError as exc:
            await events.put({'event': 'error', 'detail': str(exc)})
        except Exception:
            # Keys and upstream request headers must not enter browser error messages.
            import logging
            logging.getLogger(__name__).exception('Local avatar reply failed')
            await events.put({'event': 'error', 'detail': '回答或语音生成失败，请重试并查看服务日志'})
        finally:
            await events.put(None)

    async with session.lock:
        await cancel(session)
        if session.backend != 'live2d':
            await renderer('/interrupt_talk', json={'sessionid': body.sessionid})
        session.touched = time.monotonic()
        task = asyncio.create_task(produce())
        session.task = task

    async def stream():
        try:
            while True:
                event = await events.get()
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + '\n'
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    return StreamingResponse(stream(), media_type='application/x-ndjson', headers={'Cache-Control': 'no-store'})
