"""Host-side checks; these do not substitute for Windows installation testing."""
import ast
import errno
import json
import os
from pathlib import Path
import socket
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
from build_paths import WORK
APP = WORK / 'app/resources/app'
sys.path.insert(0, str(ROOT))
from supervisor import prepare


def main():
    for p in (ROOT / 'source').rglob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='whale-portable-test-') as directory:
        data = Path(directory)
        with socket.socket() as occupied:
            try:
                occupied.bind(('127.0.0.1', 8795))
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE:
                    raise
            ports = prepare(APP, data)
            assert ports['bridge'] != 8795
        assert len(set(ports.values())) == 4
        config = json.loads((data / 'config.json').read_text())
        assert config['llm']['model'] == 'deepseek-flash'
        assert config['llm']['thinking'] == 'disabled'
        assert config['tts']['voice'] == 'hojo_zh_f_02'
        assert 'api_key' not in config['llm']
        profile = data / 'state/characters/default/character.json'
        doc = json.loads(profile.read_text())
        doc['profile']['name'] = '蓝蓝'
        profile.write_text(json.dumps(doc, ensure_ascii=False))
        memory = profile.with_name('memory.json')
        memory.write_text('{"test":"retain"}')
        prepare(APP, data)
        assert json.loads(profile.read_text())['profile']['name'] == '蓝蓝'
        assert memory.read_text() == '{"test":"retain"}'
        memory.unlink()
        os.environ.update(VIDU_CONF=str(data / 'config.json'), CYBER_DATA_DIR=str(data),
                          CYBER_COLLECTOR_RESTART_FILE=str(data / 'collector.restart'))
        sys.path.insert(0, str(APP / 'payload/repo'))
        from fastapi.testclient import TestClient
        from src.bridge import app
        with TestClient(app) as client:
            for url in ('/local', '/local/broadcast', '/local/settings', '/api/local/health',
                        '/api/local/appearance', '/api/local/character', '/api/tts/voices'):
                response = client.get(url)
                assert response.status_code == 200, (url, response.status_code, response.text[:300])
            response = client.get('/api/local/character').json()
            assert len(response['voices']) == 16, response
            assert response['profile']['name'] == '蓝蓝'
            response['profile']['name'] = '鲸鲸'
            assert client.post('/api/local/character', json=response['profile']).status_code == 200
            assert client.get('/api/local/character').json()['profile']['name'] == '鲸鲸'
            assert client.get('/api/local/character/export').status_code == 200
            from src.local_studio_config import StudioSettings
            assert len(StudioSettings(blocked_words=[f'测试{i}' for i in range(150)]).blocked_words) == 150
            sid = client.post('/api/local/connect', json={})
            assert sid.status_code == 200, sid.text
            assert client.post('/api/local/connect', json={}).status_code == 409
            assert client.post('/api/local/connect', json={'takeover': True}).status_code == 200
        # Fresh profiles and voices are per-instance, and app install tree stays read-only.
        assert not (APP / 'payload/repo/state').exists()
        assert not (APP / 'payload/repo/logs').exists()
    print('PASS: syntax, isolated configuration, port fallback, retained identity/memory, 16 voices, pages, settings, session takeover')


if __name__ == '__main__':
    main()
