"""Entry for embedded Python: no dependency on PATH, pip, or user Python."""
import os
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parent
mode = sys.argv.pop(1)
payload = root / 'payload'
if mode == 'supervisor':
    sys.path.insert(0, str(root))
    runpy.run_module('supervisor', run_name='__main__')
elif mode == 'bridge':
    sys.path.insert(0, str(payload / 'repo'))
    runpy.run_module('src.main', run_name='__main__')
elif mode in ('80m', '40m'):
    # Set once, before native libraries or worker threads start. CreateProcessW
    # / chdirW accept Unicode roots; kaldifst reads ASCII relative descendants.
    os.chdir(root)
    sys.path.insert(0, str(root))
    try:
        from text_normalize import preflight
        preflight()
        print('VOICE_TEXT_PREFLIGHT_OK: zh/en', flush=True)
    except Exception:
        print('VOICE_STARTUP_ERROR: 文字处理组件自检失败，请打开服务日志查看具体原因。',
              file=sys.stderr, flush=True)
        raise
    service = payload / ('hojo-' + mode)
    sys.path.insert(0, str(service))
    # Hojo servers select their matching onnx_model module before importing runtimes.
    sys.argv[1:1] = ['hojo80_server:app' if mode == '80m' else 'hojo_server:app']
    runpy.run_module('uvicorn', run_name='__main__')
else:
    raise SystemExit('Unknown local service')
