"""Minimal OBS WebSocket v5 client. Requests happen only on operator actions."""
import asyncio
import base64
import hashlib
import json
import uuid
from contextlib import asynccontextmanager

from fastapi import HTTPException
from . import local_studio_config as studio


def _sha(value):
    return base64.b64encode(hashlib.sha256(value.encode()).digest()).decode()


@asynccontextmanager
async def obs_client():
    import websockets
    cfg = studio.settings()
    try:
        async with websockets.connect(cfg.obs_url, open_timeout=5, max_size=1024*1024) as socket:
            hello = json.loads(await asyncio.wait_for(socket.recv(), 5))
            if hello.get('op') != 0:
                raise ValueError('Unexpected OBS greeting')
            identify = {'rpcVersion': 1, 'eventSubscriptions': 0}
            auth = hello['d'].get('authentication')
            if auth:
                password = studio.secrets().get('obs_password', '')
                identify['authentication'] = _sha(_sha(password + auth['salt']) + auth['challenge'])
            await socket.send(json.dumps({'op': 1, 'd': identify}))
            accepted = json.loads(await asyncio.wait_for(socket.recv(), 5))
            if accepted.get('op') != 2:
                raise ValueError('OBS identification failed')

            async def request(kind, data=None):
                rid = str(uuid.uuid4())
                await socket.send(json.dumps({'op': 6, 'd': {'requestType': kind,
                    'requestId': rid, 'requestData': data or {}}}))
                while True:
                    response = json.loads(await asyncio.wait_for(socket.recv(), 8))
                    if response.get('op') == 7 and response.get('d', {}).get('requestId') == rid:
                        body = response['d']
                        if not body['requestStatus']['result']:
                            # Do not echo requestData, which may include a stream key.
                            raise HTTPException(502, f'OBS未完成{kind}（错误码{body["requestStatus"].get("code")}）')
                        return body.get('responseData') or {}
            yield request
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, '无法连接OBS，请检查电脑地址、4455端口、WebSocket开关和密码') from exc


async def check():
    async with obs_client() as request:
        version = await request('GetVersion')
        stream = await request('GetStreamStatus')
        return {'ok': True, 'version': version.get('obsVersion'),
                'streaming': bool(stream.get('outputActive')), 'reconnecting': bool(stream.get('outputReconnecting'))}


async def setup():
    cfg = studio.settings()
    if not cfg.stage_url:
        raise HTTPException(422, '先填写OBS电脑可访问的直播画面地址')
    key = studio.secrets().get('stream_key', '')
    if cfg.stream_server and not key:
        raise HTTPException(422, '已填写推流地址，还需要推流密钥')
    async with obs_client() as request:
        streaming = await request('GetStreamStatus')
        recording = await request('GetRecordStatus')
        if streaming.get('outputActive') or recording.get('outputActive'):
            raise HTTPException(409, '请先在OBS停止推流和录制，再配置画布与场景')
        width, height = (1080, 1920) if cfg.orientation == 'portrait' else (1920, 1080)
        await request('SetVideoSettings', {'baseWidth': width, 'baseHeight': height,
                                         'outputWidth': width, 'outputHeight': height,
                                         'fpsNumerator': 30, 'fpsDenominator': 1})
        scenes = await request('GetSceneList')
        if cfg.obs_scene not in {s['sceneName'] for s in scenes.get('scenes', [])}:
            await request('CreateScene', {'sceneName': cfg.obs_scene})
        source = cfg.obs_scene + ' · 画面与声音'
        inputs = (await request('GetInputList')).get('inputs', [])
        existing = next((i for i in inputs if i['inputName'] == source), None)
        settings = {'url': cfg.stage_url, 'width': width, 'height': height, 'reroute_audio': True,
                    'shutdown': True, 'restart_when_active': False, 'fps': 30}
        if existing:
            if existing.get('unversionedInputKind', existing.get('inputKind')) != 'browser_source':
                raise HTTPException(409, 'OBS已有同名非浏览器来源，请更换场景名称')
            await request('SetInputSettings', {'inputName': source, 'inputSettings': settings, 'overlay': True})
            items = (await request('GetSceneItemList', {'sceneName': cfg.obs_scene})).get('sceneItems', [])
            if source not in {x['sourceName'] for x in items}:
                await request('CreateSceneItem', {'sceneName': cfg.obs_scene, 'sourceName': source, 'sceneItemEnabled': True})
        else:
            await request('CreateInput', {'sceneName': cfg.obs_scene, 'inputName': source,
                                         'inputKind': 'browser_source', 'inputSettings': settings,
                                         'sceneItemEnabled': True})
        await request('SetInputMute', {'inputName': source, 'inputMuted': False})
        await request('SetInputAudioMonitorType', {'inputName': source, 'monitorType': 'OBS_MONITORING_TYPE_NONE'})
        await request('SetCurrentProgramScene', {'sceneName': cfg.obs_scene})
        if cfg.stream_server:
            await request('SetStreamServiceSettings', {'streamServiceType': 'rtmp_custom',
                'streamServiceSettings': {'server': cfg.stream_server, 'key': key, 'use_auth': False}})
        return {'ok': True, 'scene': cfg.obs_scene, 'source': source, 'width': width, 'height': height,
                'streaming_started': False}


async def start_stop(start):
    async with obs_client() as request:
        state = await request('GetStreamStatus')
        if bool(state.get('outputActive')) != start:
            await request('StartStream' if start else 'StopStream')
        return {'ok': True, 'requested': 'start' if start else 'stop',
                'status': await request('GetStreamStatus')}
