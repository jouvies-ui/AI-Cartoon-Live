"""Local livestream: collector -> bounded audience queue -> acknowledged browser playback."""
from __future__ import annotations
import asyncio
import contextlib
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from collections import deque

import httpx
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from . import local_avatar as avatar, local_studio_config as config, local_obs
from .llm import LLMClient

router = APIRouter()


def collector_message(msg):
    if not isinstance(msg, dict) or msg.get('type') == 'system':
        return None
    method = msg.get('method')
    user = msg.get('user') or {}
    nick = user.get('nickname', '') if isinstance(user, dict) else ''
    common = msg.get('common') or {}
    event_id = str(common.get('msgId') or msg.get('msgId') or '') if isinstance(common, dict) else ''
    if method == 'WebcastChatMessage':
        return {'nick': nick, 'content': msg.get('content', ''), 'text': msg.get('content', ''),
                'kind': 'chat', 'platform': '抖音', 'event_id': event_id}
    if method in {'WebcastGiftMessage', 'WebcastLightGiftMessage', 'WebcastBindingGiftMessage'}:
        inner = msg.get('msg') if method == 'WebcastBindingGiftMessage' else msg
        if not isinstance(inner, dict):
            return None
        gift = inner.get('gift') or {}
        if not isinstance(gift, dict):
            return None
        if inner.get('groupId') and str(inner.get('repeatEnd', 0)) != '1':
            return None
        def number(key):
            try:return max(0, int(inner.get(key) or 0))
            except (TypeError, ValueError):return 0
        user = inner.get('user') or {}
        if not isinstance(user, dict):
            user = {}
        return {'nick': user.get('nickname') or nick, 'kind': 'gift', 'platform': '抖音',
                'gift_item': gift.get('name', ''), 'gift_num': max(number('repeatCount'), number('comboCount'), number('count'), 1),
                'event_id': event_id}
    return None


class StudioRuntime:
    def __init__(self):
        self.enabled = False
        self.player = None
        self.player_suspended = False
        self.player_task = None
        self.player_done = asyncio.Event()
        self.player_done.set()
        self.sid = None
        self.collector_task = None
        self.current_task = None
        self.queue = deque(maxlen=12)
        #主播口播是独立的高优先级队列。它可以打断当前弹幕回复，且
        # pump 永远先消费这里，再继续普通弹幕队列。
        self.operator_queue = deque(maxlen=8)
        self.wake = asyncio.Event()
        self.ack = asyncio.Event()
        self.turn_id = None
        self.player_ready = False
        self.lock = asyncio.Lock()
        self.control_lock = asyncio.Lock()
        self.send_lock = asyncio.Lock()
        self.recent = {}
        self.events = deque(maxlen=40)
        self.counts = {'received': 0, 'queued': 0, 'answered': 0, 'filtered': 0, 'dropped': 0, 'duplicates': 0}
        self.collector_state = 'stopped'
        self.room_state = 'unconfigured'
        self.last_error = ''
        self.room_info = {}
        self.real_received = 0
        self.test_received = 0
        self.reply_phase = 'idle'
        self.last_latency = None
        self.current_text = ''
        self.current_source = ''

    def readiness(self):
        cfg = config.settings()
        issues = []
        def add(code, text):issues.append({'code': code, 'text': text})
        if not self.enabled:add('paused', '互动尚未开始，点击“保存并开始互动”。')
        if cfg.input_mode == 'direct':
            if not cfg.room:add('room_missing', '粘贴抖音直播间链接或房间号。')
            elif self.room_state in {'offline', 'ended'}:
                add('room_offline', '抖音返回未开播 / 已下播；保持连接等待开播。若手机上正在直播，请核对链接并重新检测房间。')
            elif self.room_state in {'account_offline', 'account_no_room'}:
                add('account_no_room', '识别到账号，但没有当前直播间；请从正在直播的页面复制链接。')
            elif self.room_state == 'not_found':add('room_invalid', '未找到直播间，请重新复制直播间链接。')
            elif self.room_state != 'online':add('room_unverified', '尚未确认抖音消息连接；可点击“检测房间”查看原因。')
            if self.enabled and self.collector_state != 'connected':add('collector_unavailable', '采集插件尚未连接，正在检查或重连。')
        if self.player is None:
            add('player_missing', '直播画面未连接；点击“保存并开始互动”会自动结束私人聊天并打开画面，记忆保留。')
        elif not self.player_ready:add('audio_blocked', '请点击下方人物画面中的“启用声音”，浏览器尚未允许播放。')
        if not cfg.answer_chat:add('chat_disabled', '自动回答弹幕已关闭；勾选后保存即可回答观众。')
        return issues

    def status(self):
        return {'enabled': self.enabled, 'player_connected': self.player is not None,
                'player_suspended': self.player_suspended,
                'private_chat_connected': any(not s.audience for s in avatar._sessions.values()),
                'player_audio_ready': self.player_ready, 'busy': self.turn_id is not None,
                'queue_size': len(self.queue), 'operator_queue_size': len(self.operator_queue),
                'operator_active': self.current_source == 'operator' and self.turn_id is not None,
                'current_text': self.current_text, 'current_source': self.current_source,
                'collector': self.collector_state,
                'room': self.room_state, 'last_error': self.last_error,
                'room_info': dict(self.room_info), 'issues': self.readiness(),
                'ready': not self.readiness(), 'real_received': self.real_received,
                'test_received': self.test_received,
                'reply_phase': self.reply_phase, 'last_latency': self.last_latency,
                'counts': dict(self.counts), 'events': list(self.events)}

    async def send(self, value):
        if self.player:
            async with self.send_lock:
                await self.player.send_json(value)

    def note(self, kind, text):
        self.events.append({'kind': kind, 'text': text[:240], 'at': time.time()})

    async def enqueue(self, payload, test=False):
        cfg = config.settings()
        if not test and not self.enabled:
            return {'ok': False, 'queued': False, 'reason': 'disabled'}
        self.counts['received'] += 1
        if test:self.test_received += 1
        else:self.real_received += 1
        kind = 'gift' if payload.get('kind') in {'gift', 'gifts'} else 'chat'
        nick = str(payload.get('nick') or '观众').strip()[:32]
        content = str(payload.get('content') or payload.get('text') or '').strip()
        item = str(payload.get('gift_item') or '').strip()[:40]
        if (kind == 'chat' and (not cfg.answer_chat or not content or len(content) > cfg.max_chars)
            or kind == 'gift' and (not cfg.thank_gifts or not item)
            or any(w.casefold() in (nick + content + item).casefold() for w in cfg.blocked_words)):
            self.counts['filtered'] += 1
            return {'ok': True, 'queued': False, 'reason': 'filtered'}
        try:num = max(1, min(int(payload.get('gift_num') or 1), 10000))
        except (TypeError, ValueError):num = 1
        if kind == 'chat':
            item, num = '', 0
        else:
            content = ''
        event = {'nick': nick, 'content': content[:500], 'kind': kind,
                 'gift_item': item, 'gift_num': num, 'test': test}
        now = time.monotonic()
        self.recent = {k: v for k, v in self.recent.items() if now - v < 120}
        ident = str(payload.get('event_id') or '')[:100]
        key = ('id:' + ident) if ident else hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        window = 120 if ident else 5
        if now - self.recent.get(key, -1000) < window:
            self.counts['duplicates'] += 1
            return {'ok': True, 'queued': False, 'reason': 'duplicate'}
        self.recent[key] = now
        if len(self.recent) > 2048:
            self.recent.pop(next(iter(self.recent)))
        if self.player is None or not self.player_ready:
            self.counts['dropped'] += 1
            return {'ok': False, 'queued': False, 'reason': 'no_audio_player'}
        if len(self.queue) == self.queue.maxlen:
            # Drop an older chat before a gift, while keeping memory bounded.
            index = next((i for i, old in enumerate(self.queue) if old['kind'] == 'chat'), 0)
            del self.queue[index]
            self.counts['dropped'] += 1
        self.queue.append(event)
        self.counts['queued'] += 1
        self.note('test' if test else kind, f'{nick}：' + (content if kind == 'chat' else f'{item} × {num}'))
        self.wake.set()
        return {'ok': True, 'queued': True, 'reason': 'queued'}

    async def enqueue_operator(self, text: str):
        """Queue a host-directed line and give it immediate playback priority."""
        text = str(text or '').strip()
        if not text:
            return {'ok': False, 'queued': False, 'reason': 'empty'}
        if self.player is None or not self.player_ready:
            return {'ok': False, 'queued': False, 'reason': 'no_audio_player'}
        async with self.control_lock:
            # A host line is an explicit interruption. Stop browser playback
            # first, then cancel model/TTS work so no stale audio can follow.
            current = self.current_task
            interrupted = bool(current and not current.done())
            if current and not current.done():
                with contextlib.suppress(Exception):
                    await self.send({'event': 'stop'})
                current.cancel()
                await asyncio.gather(current, return_exceptions=True)
                self.current_task = None
            if len(self.operator_queue) == self.operator_queue.maxlen:
                self.operator_queue.popleft()
                self.counts['dropped'] += 1
            self.operator_queue.append({'content': text[:1000], 'kind': 'operator',
                                        'test': False, 'nick': '主播'})
            self.note('operator', '主播口播：' + text[:220])
            self.wake.set()
        return {'ok': True, 'queued': True, 'reason': 'operator_priority',
                'interrupted': interrupted,
                'queue_size': len(self.operator_queue)}

    async def collector(self):
        import websockets
        delay = 3
        try:
            while self.enabled:
                cfg = config.settings()
                url = cfg.collector_url.replace('https://', 'wss://', 1).replace('http://', 'ws://', 1) + '/ws/' + cfg.room
                token = config.secrets().get('collector_token', '')
                headers = {'Authorization': 'Bearer ' + token} if token else {}
                self.collector_state = 'connecting'
                try:
                    async with websockets.connect(url, additional_headers=headers, open_timeout=8,
                                                  ping_interval=20, max_size=1024*1024) as ws:
                        self.collector_state = 'connected'
                        self.room_state = 'waiting_status'
                        self.room_info = {}
                        self.last_error = ''
                        delay = 3
                        async for raw in ws:
                            try:msg = json.loads(raw)
                            except (ValueError, TypeError):continue
                            if isinstance(msg, dict) and msg.get('type') == 'system':
                                if msg.get('event') != 'live_status':continue
                                state = msg.get('status')
                                self.room_state = state if state in {'online','offline','ended','not_found','unknown','error','account_offline','account_no_room'} else 'unknown'
                                self.room_info = {'anchor': str(msg.get('live_name') or '')[:80],
                                                  'title': str(msg.get('title') or '')[:160],
                                                  'checked_at': time.time()}
                                if self.room_state == 'not_found':
                                    self.last_error = '直播间不存在，请核对房间号'
                                    return
                                continue
                            event = collector_message(msg)
                            if event:
                                self.room_state = 'online'
                                await self.enqueue(event)
                        self.collector_state = 'reconnecting'
                        self.room_state = 'unknown'
                except asyncio.CancelledError:raise
                except Exception:
                    self.collector_state = 'reconnecting'
                    self.room_state = 'unknown'
                    self.last_error = '采集器连接未成功，正在重连；请检查地址、服务状态和访问令牌'
                await asyncio.sleep(delay)
                delay = min(30, delay + 3)
        finally:
            self.collector_state = 'stopped'

    async def enable(self):
        cfg = config.settings()
        if cfg.input_mode == 'direct' and not cfg.room:
            raise HTTPException(422, '请先填写直播间号并保存')
        self.enabled = True
        self.last_error = ''
        if cfg.input_mode == 'direct' and (not self.collector_task or self.collector_task.done()):
            self.collector_task = asyncio.create_task(self.collector())
        elif cfg.input_mode == 'relay':
            self.collector_state = 'external_relay'
        return self.status()

    async def pause(self):
        self.enabled = False
        self.queue.clear()
        self.operator_queue.clear()
        if self.collector_task:
            self.collector_task.cancel()
            await asyncio.gather(self.collector_task, return_exceptions=True)
            self.collector_task = None
        if self.current_task:
            self.current_task.cancel()
            await asyncio.gather(self.current_task, return_exceptions=True)
        self.turn_id = None
        self.current_text = ''
        self.current_source = ''
        self.reply_phase = 'idle'
        self.ack.set()
        self.collector_state = 'stopped'
        with contextlib.suppress(Exception):await self.send({'event': 'stop'})
        return self.status()

    async def process(self, event):
        self.turn_id = str(uuid.uuid4())
        self.ack.clear()
        turn = self.turn_id
        self.last_error = ''
        self.reply_phase = 'thinking'
        self.current_text = event.get('content') or ''
        self.current_source = event.get('kind') or 'chat'
        try:
            await self.send({'event': 'turn', 'turn_id': turn})
            if event.get('kind') == 'operator':
                response = await avatar.chat(avatar.ChatBody(sessionid=self.sid,
                    text=event['content'], mode='say'))
            else:
                payload = {key: event[key] for key in ('nick','kind','content','gift_item','gift_num')}
                if config.settings().read_chat and event['kind'] == 'chat':
                    payload['instruction'] = '先简短复述这位观众的提问再回应，不要逐字念出网址、代码或设置命令。'
                response = await avatar.chat(avatar.ChatBody(sessionid=self.sid, text=json.dumps(payload, ensure_ascii=False)))
            duration = 0.0
            import base64
            async for line in response.body_iterator:
                value = json.loads(line)
                if value['event'] == 'error':
                    self.last_error = value.get('detail') or '对话或语音生成失败，请稍后重试'
                    raise RuntimeError('synthesis failed')
                if value['event'] == 'audio_chunk':
                    self.reply_phase = 'speaking'
                    duration += max(0, len(base64.b64decode(value['wav'])) - 44) / 48000
                if value['event'] == 'plan':self.reply_phase = 'synthesizing'
                if value['event'] == 'audio':
                    self.last_latency = {key: value[key] for key in
                                         ('seconds', 'model_seconds', 'first_tts_seconds') if key in value}
                await self.send({**value, 'turn_id': turn})
            await self.send({'event': 'turn_end', 'turn_id': turn})
            await asyncio.wait_for(self.ack.wait(), timeout=max(30, duration + 20))
            if self.turn_id == turn:
                self.counts['answered'] += 1
        except asyncio.CancelledError:
            if self.sid in avatar._sessions:
                await avatar.cancel(avatar._sessions[self.sid])
            raise
        except Exception:
            self.last_error = self.last_error or '本条互动未完成，请检查语音服务和直播画面声音状态'
            self.note('error', self.last_error)
            with contextlib.suppress(Exception):await self.send({'event':'stop'})
        finally:
            self.turn_id = None
            self.reply_phase = 'idle'
            self.current_text = ''
            self.current_source = ''

    async def pump(self):
        while self.player is not None:
            await self.wake.wait()
            if not self.operator_queue and not self.queue:
                self.wake.clear()
                continue
            event = self.operator_queue.popleft() if self.operator_queue else self.queue.popleft()
            if event.get('kind') != 'operator' and not self.enabled and not event['test']:
                continue
            self.current_task = asyncio.create_task(self.process(event))
            try:await self.current_task
            except asyncio.CancelledError:
                if self.player is None:raise
            finally:self.current_task = None
            await asyncio.sleep(config.settings().reply_gap)

    async def release_player(self):
        """Called under control_lock when the operator switches to chat."""
        self.player_suspended = True
        await self.pause()
        player, task, done = self.player, self.player_task, self.player_done
        if player is None:
            return
        with contextlib.suppress(Exception):
            await self.send({'event': 'released', 'detail': '已切换到聊天，直播画面连接已释放。'})
            await player.close(code=1000)
        try:
            await asyncio.wait_for(done.wait(), 3)
        except asyncio.TimeoutError:
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def playback(self, ws):
        await ws.accept()
        async with self.control_lock, self.lock:
            if self.player_suspended:
                await ws.send_json({'event': 'released',
                    'detail': '已切换到聊天。需要直播时，请在设置页重新开始互动或演练。'})
                await ws.close(code=1000)
                return
            if self.player is not None:
                await ws.send_json({'event':'unavailable','detail':'已有直播画面连接，请关闭另一个预览或OBS来源'})
                await ws.close(code=1008)
                return
            async with avatar._connect_lock:
                if avatar._sessions:
                    await ws.send_json({'event':'unavailable','detail':'请先断开私人聊天，再使用直播画面'})
                    await ws.close(code=1008)
                    return
                self.sid = str(uuid.uuid4())
                avatar._sessions[self.sid] = avatar.Session(backend='live2d', audience=True,
                    llm=LLMClient(config.audience_llm_conf))
            self.player = ws
            self.player_task = asyncio.current_task()
            self.player_done = done = asyncio.Event()
            session_id = self.sid
            self.player_ready = False
            self.queue.clear()
            self.operator_queue.clear()
        worker = asyncio.create_task(self.pump())
        try:
            await self.send({'event':'connected','sessionid':self.sid,
                             'settings':public_stage_settings()})
            while True:
                msg = await asyncio.wait_for(ws.receive_json(), 50)
                if not isinstance(msg, dict):continue
                if self.sid not in avatar._sessions:break
                avatar._sessions[self.sid].touched = time.monotonic()
                if msg.get('event') == 'ready':self.player_ready = msg.get('audio') is True
                if msg.get('event') == 'played' and msg.get('turn_id') == self.turn_id:
                    self.ack.set()
        except (WebSocketDisconnect, asyncio.TimeoutError):pass
        except (asyncio.CancelledError, RuntimeError):
            if not self.player_suspended:
                raise
        finally:
            # Hold the admission lock through cleanup. An older websocket
            # must never clear the session/worker belonging to its successor.
            async with self.lock:
                try:
                    self.player = None
                    self.player_ready = False
                    self.queue.clear()
                    self.operator_queue.clear()
                    worker.cancel()
                    current = self.current_task
                    if current:current.cancel()
                    await asyncio.gather(worker, return_exceptions=True)
                    if current:await asyncio.gather(current, return_exceptions=True)
                    await avatar.close_session(session_id)
                    self.sid = None
                    self.turn_id = None
                    self.current_task = None
                    self.player_task = None
                finally:
                    done.set()


runtime = StudioRuntime()


def public_stage_settings():
    cfg = config.settings()
    return {key: getattr(cfg, key) for key in ('background','subtitles','orientation')}


@router.on_event('shutdown')
async def shutdown():
    await runtime.pause()
    if runtime.player:
        with contextlib.suppress(Exception):await runtime.player.close()


@router.get('/api/local/studio')
async def get_settings():
    return {'settings': config.settings().model_dump(), 'secrets': config.secret_flags(),
            'managed_collector': config.collector_config_path() is not None, 'runtime': runtime.status()}


@router.post('/api/local/studio')
async def save_settings(value: config.StudioSettings):
    was_enabled = runtime.enabled
    await runtime.pause()
    config.save_settings(value)
    with contextlib.suppress(Exception):
        await runtime.send({'event':'settings','settings':public_stage_settings()})
    if was_enabled:await runtime.enable()
    return await get_settings()


@router.post('/api/local/studio/secrets')
async def save_secrets(request: Request):
    # Default validation errors include input values. Never echo a submitted
    # credential, even when it has invalid characters or an invalid type.
    try:
        value = config.StudioSecrets.model_validate(await request.json())
    except (ValueError, TypeError):
        raise HTTPException(422, '凭据格式不正确：请使用单行文字，并检查长度与字段名称')
    try:
        updates = config.save_secrets(value)
        path = config.collector_config_path()
        if path and {'douyin_cookie','collector_token'} & updates.keys():
            import yaml
            data = yaml.safe_load(path.read_text())
            saved = config.secrets()
            data.setdefault('cookie', {})['douyin'] = saved.get('douyin_cookie', '')
            data.setdefault('api', {})['key'] = saved.get('collector_token', '')
            # JSON is a YAML subset; reuse our atomic private-file writer.
            config._write(path, data)
            restart_file = os.environ.get('CYBER_COLLECTOR_RESTART_FILE')
            if restart_file:
                # The desktop supervisor owns this process, without systemd/WSL.
                Path(restart_file).write_text(str(time.time_ns()), encoding='utf-8')
            else:
                service = config.collector_service()
                proc = await asyncio.create_subprocess_exec('systemctl','--user','restart',service,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                try:
                    await asyncio.wait_for(proc.wait(), 15)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise HTTPException(502, '凭据已保存，但采集插件重启超时，请检测采集器状态')
                if proc.returncode:
                    raise HTTPException(502, '凭据已保存，但采集插件重启失败，请查看本机服务状态')
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(502, '凭据保存或采集插件配置失败，请检查服务器文件与服务权限') from exc
    return {'ok':True,'secrets':config.secret_flags()}


@router.get('/api/local/studio/status')
async def status():return runtime.status()


@router.post('/api/local/studio/enable')
async def enable():return await runtime.enable()


class StartRequest(BaseModel):
    settings: config.StudioSettings | None = None
    collect: bool = True


@router.post('/api/local/studio/start')
async def start_interaction(body: StartRequest):
    """An explicit operator action switches to an isolated public session."""
    async with runtime.control_lock:
        cfg = body.settings or config.settings()
        if body.collect and cfg.input_mode == 'direct' and not cfg.room:
            raise HTTPException(422, '请填写直播间链接，或点击“先用模拟弹幕试一试”。')
        if body.settings is not None and cfg != config.settings():
            await runtime.pause()
            config.save_settings(cfg)
            await runtime.send({'event': 'settings', 'settings': public_stage_settings()})
        async with avatar._connect_lock:
            for sid, session in list(avatar._sessions.items()):
                if not session.audience:
                    await avatar.close_session(sid)
        runtime.player_suspended = False
        if body.collect:await runtime.enable()
        return await get_settings()


class RoomCheck(BaseModel):
    room: str = Field(max_length=200)


@router.post('/api/local/studio/room-check')
async def room_check(body: RoomCheck):
    try:room = config.StudioSettings(room=body.room).room
    except ValueError:raise HTTPException(422, '请填写 live.douyin.com 的完整直播间链接或房间号。')
    if not room:raise HTTPException(422, '请先填写直播间链接或房间号。')
    token = config.secrets().get('collector_token', '')
    headers = {'Authorization': 'Bearer '+token} if token else {}
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
            response = await client.get(config.settings().collector_url+'/api/v1/rooms/'+room, headers=headers)
        if response.status_code == 401:raise HTTPException(401, '采集器拒绝访问，请检查高级设置中的访问令牌。')
        data = response.json().get('data') or {}
        state = data.get('status', 'unknown')
        if response.status_code == 404:state = 'not_found'
        if state not in {'online', 'offline', 'account_no_room', 'not_found'}:state = 'unknown'
        anchor = data.get('anchor') or {}
        detail = {
            'online': '抖音确认已开播。开始互动后等待采集连接就绪，再发送一条真实弹幕验证。',
            'offline': '抖音当前返回未开播 / 已下播。可以先做本地演练；开始互动后会自动等待开播。直播标题不能代表开播状态。',
            'account_no_room': '识别到账号，但当前没有直播间；请从正在直播的页面复制完整链接。',
            'not_found': '未找到该直播间，请核对链接；不要填写抖音账号 ID 或作品链接。',
            'unknown': '暂时无法确认房间状态，可能是网络、平台验证或登录限制。请先在浏览器确认链接能打开，再重试；需要登录时可在高级设置填写 Cookie。',
        }[state]
        return {'room': room, 'status': state, 'anchor': str(anchor.get('nickname') or '')[:80],
                'title': str(data.get('title') or '')[:160], 'detail': detail}
    except HTTPException:raise
    except Exception:
        raise HTTPException(502, '房间检测未完成，请检查采集插件连接或稍后重试。')


@router.post('/api/local/studio/pause')
async def pause():return await runtime.pause()


@router.post('/api/local/studio/collector-check')
async def collector_check():
    cfg = config.settings()
    token = config.secrets().get('collector_token', '')
    headers = {'Authorization':'Bearer '+token} if token else {}
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            health = await client.get(cfg.collector_url+'/api/v1/health',headers=headers)
            if health.status_code == 401:
                raise HTTPException(401,'采集器拒绝访问，请检查访问令牌')
            health.raise_for_status()
            health.json()
        return {'ok':True,'detail':'采集插件可连接；真实房间状态在启用互动后显示'}
    except HTTPException:raise
    except Exception as exc:raise HTTPException(502,'无法连接采集器，请检查服务地址和端口') from exc


class TestEvent(BaseModel):
    kind: str = 'chat'
    text: str = Field(default='你好，介绍一下你自己，再点点头。',min_length=1,max_length=500)


@router.post('/api/local/studio/test')
async def test_event(body: TestEvent):
    if body.kind not in {'chat','gift'}:raise HTTPException(422,'只支持弹幕或礼物测试')
    result = await runtime.enqueue({'kind':body.kind,'nick':'本地测试观众','text':body.text,
                                   'gift_item':'小星星','gift_num':1},test=True)
    if result['reason'] == 'no_audio_player':raise HTTPException(409,'请先打开直播画面并启用声音；OBS和浏览器预览只保留一个')
    return result


class OperatorSay(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.post('/api/local/studio/say')
async def operator_say(body: OperatorSay):
    result = await runtime.enqueue_operator(body.text)
    if result['reason'] == 'no_audio_player':
        raise HTTPException(409, '请先打开直播画面并启用声音；主播口播需要当前画面连接')
    if result['reason'] == 'empty':
        raise HTTPException(422, '请输入要口播的文字')
    return result


@router.websocket('/api/local/studio/player')
async def player(ws: WebSocket):await runtime.playback(ws)


@router.post('/api/local/studio/obs/check')
async def obs_check():return await local_obs.check()


@router.post('/api/local/studio/obs/setup')
async def obs_setup():return await local_obs.setup()


@router.post('/api/local/studio/obs/start')
async def obs_start():
    if runtime.player is None or not runtime.player_ready:
        raise HTTPException(409,'直播画面或声音尚未连接，请先配置OBS来源')
    return await local_obs.start_stop(True)


@router.post('/api/local/studio/obs/stop')
async def obs_stop():return await local_obs.start_stop(False)
