"""Own local child processes and portable per-user state on Windows."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def available_port(preferred, reserved):
    for port in range(preferred, preferred + 100):
        if port in reserved:
            continue
        with socket.socket() as s:
            try:
                s.bind(('127.0.0.1', port))
            except OSError:
                continue
            reserved.add(port)
            return port
    raise RuntimeError('没有可用的本机端口，请关闭占用端口的程序。')


def prepare(root, data):
    payload = root / 'payload'
    data.mkdir(parents=True, exist_ok=True)
    # First-run seed only: upgrading/relaunching never overwrites voices or memory.
    for voice in (payload / 'voices').iterdir():
        target = data / 'voices' / voice.name
        if voice.is_dir() and not target.exists():
            shutil.copytree(voice, target)
    profile_path = data / 'state/characters/default/character.json'
    if not profile_path.exists():
        profile = json.loads((payload / 'character-default.json').read_text(encoding='utf-8'))
        write_json(profile_path, {'version': 2, 'character_id': 'default', 'revision': 1,
                                 'previous_names': [], 'profile': profile})
    reserved = set()
    ports = {name: available_port(port, reserved) for name, port in
             [('bridge', 8795), ('80m', 9881), ('40m', 9880), ('collector', 1089)]}
    url = lambda name: f'http://127.0.0.1:{ports[name]}'
    conf_path = data / 'config.json'
    conf = json.loads(conf_path.read_text(encoding='utf-8')) if conf_path.exists() else {}
    conf.update(vidu={'api_key': ''}, local_avatar={
        'backend': 'live2d', 'avatar': 'whale_girl_v1', 'character_id': 'default',
        'collector_config': str(data / 'collector.json')}, bridge={'port': ports['bridge']})
    conf['llm'] = {'model': 'deepseek-flash',
        'base_url': 'https://api.deepseek.com',
        'key_file': '', 'thinking': 'disabled', 'history_turns': 12,
        'fallback_models': [], 'max_tokens': 1100}
    manifest = json.loads((payload / 'hojo-80m/model-manifest.json').read_text(encoding='utf-8'))
    conf['tts'] = {'engine': 'hojo', 'hojo_variant': '80m', 'hojo_base': url('80m'),
        'hojo_builtin_base': url('40m'), 'hojo_voices_dir': str(data / 'voices'),
        'hojo_model_revision': manifest['model_revision'], 'hojo_timeout_sec': 90,
        'voice': json.loads(profile_path.read_text(encoding='utf-8'))['profile']['voice_template'],
        'health': {'enabled': False}}
    write_json(conf_path, conf)
    studio_path = data / 'state/studio/settings.json'
    studio = json.loads(studio_path.read_text(encoding='utf-8')) if studio_path.exists() else {}
    studio.update(collector_url=url('collector'), stage_url=url('bridge') + '/local/broadcast')
    write_json(studio_path, studio)
    secrets_path = data / 'state/studio/secrets.json'
    credentials = json.loads(secrets_path.read_text(encoding='utf-8')) if secrets_path.exists() else {}
    credentials.setdefault('collector_token', secrets.token_urlsafe(32))
    write_json(secrets_path, credentials)
    write_json(data / 'collector.json', {'port': str(ports['collector']),
        'api': {'key': credentials['collector_token']},
        'websocket': {'allowed_origins': [url('bridge')]},
        'cookie': {'douyin': credentials.get('douyin_cookie', ''), 'use_stored': True},
        'sign': {'provider': 'local'}, 'log': {'level': 'warn'}})
    return ports


def run(root, data, parent):
    import psutil
    ports = prepare(root, data)
    payload = root / 'payload'
    log_dir = data / 'logs'; log_dir.mkdir(exist_ok=True)
    status_path = data / 'runtime.json'
    children, handles = {}, []
    closing = data / 'stop.request'
    closing.unlink(missing_ok=True)
    restart_file = data / 'collector.restart'
    marker = restart_file.read_bytes() if restart_file.exists() else b''
    env = dict(os.environ, VIDU_CONF=str(data / 'config.json'), CYBER_DATA_DIR=str(data),
        PYTHONUTF8='1', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1',
        NUMBA_CACHE_DIR=str(data / 'cache/numba'), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
        HOJO_THREADS=str(min(4, max(1, (os.cpu_count() or 2) // 2))),
        HOJO_FFMPEG=str(payload / 'bin/ffmpeg.exe'), HOJO_VOICES_DIR=str(data / 'voices'),
        HOJO_CACHE_DIR=str(data / 'cache/reference-v1'),
        CYBER_COLLECTOR_RESTART_FILE=str(restart_file),
        PATH=str(payload / 'bin') + os.pathsep + os.environ.get('PATH', ''))
    def status(phase, message):
        write_json(status_path, {'phase': phase, 'message': message, 'ports': ports,
                                'url': f'http://127.0.0.1:{ports["bridge"]}', 'pid': os.getpid()})
    def start(name):
        # Keep prior log lines for troubleshooting, but only diagnose this run.
        failure_offsets[name] = (log_dir / (name + '.log')).stat().st_size if (log_dir / (name + '.log')).exists() else 0
        output = open(log_dir / (name + '.log'), 'ab'); handles.append(output)
        if name == 'collector':
            command = [str(payload / 'bin/douyinLive.exe'), '--config', str(data / 'collector.json')]
            child_env = {k:v for k,v in env.items() if k != 'DEEPSEEK_API_KEY'}
        else:
            command = [sys.executable, '-X', 'utf8', str(root / 'python_entry.py'), name,
                       '--host', '127.0.0.1', '--port', str(ports[name])]
            if name == 'bridge': command.append('--no-browser')
            else: command += ['--no-access-log']
            child_env = dict(env, HOJO_ROOT=str(payload / ('hojo-' + name)),
                             HOJO_CPU_VARIANT='int8-v1' if name == '80m' else 'original')
            if name != 'bridge': child_env.pop('DEEPSEEK_API_KEY', None)
        children[name] = subprocess.Popen(command, cwd=data, env=child_env, stdout=output,
            stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    def stop(name):
        child = children.pop(name, None)
        if child and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=8)
            except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=5)
    def wait_ready(name, path='/health', timeout=120):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not psutil.pid_exists(parent) or closing.exists():
                raise RuntimeError('启动已取消')
            if children[name].poll() is not None:
                if name in ('40m', '80m'):
                    with (log_dir / (name + '.log')).open('rb') as stream:
                        stream.seek(failure_offsets[name])
                        log = stream.read().decode('utf-8', errors='replace')
                    if 'VOICE_STARTUP_ERROR:' in log:
                        raise RuntimeError(f'{name} 语音文字处理自检失败，请在服务日志中查看 logs/{name}.log。')
                raise RuntimeError(f'{name} 启动失败，请在服务页面打开日志。')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{ports[name]}{path}', timeout=1) as r:
                    if r.status == 200: return
            except (OSError, ValueError): pass
            time.sleep(.3)
        raise RuntimeError(f'{name} 启动超时，请检查服务日志。')
    failure_offsets = {}
    try:
        status('starting', '正在加载本机语音模型…')
        start('80m'); wait_ready('80m')
        status('starting', '正在加载全部预置音色…')
        start('40m'); wait_ready('40m')
        start('collector')
        status('starting', '正在启动数字人和直播工作台…')
        start('bridge'); wait_ready('bridge', '/api/local/health')
        status('ready', '本机服务已就绪')
        while psutil.pid_exists(parent) and not closing.exists():
            current = restart_file.read_bytes() if restart_file.exists() else b''
            if current != marker:
                marker = current; stop('collector'); start('collector')
            for name, child in list(children.items()):
                if child.poll() is not None:
                    raise RuntimeError(f'{name} 服务已退出，请重新启动本机服务并查看日志。')
            time.sleep(.5)
    except Exception as exc:
        status('error', str(exc))
        raise
    finally:
        for name in list(reversed(children)): stop(name)
        for handle in handles: handle.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True, type=Path)
    parser.add_argument('--parent', required=True, type=int)
    args = parser.parse_args()
    run(Path(__file__).resolve().parent, args.data, args.parent)
