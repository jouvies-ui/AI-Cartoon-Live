"""Exercise supervisor error reporting with real short-lived child processes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
from build_paths import WORK
APP = WORK / 'app/resources/app'

with tempfile.TemporaryDirectory(prefix='whale-startup-errors-') as directory:
    root = Path(directory)
    data = root / '用户数据'; data.mkdir()
    payload = root / 'payload'; payload.mkdir()
    for name in ('voices', 'character-default.json', 'hojo-80m'):
        (payload / name).symlink_to(APP / 'payload' / name)
    shutil.copy2(ROOT / 'supervisor.py', root / 'supervisor.py')
    for marker, expected in [(True, '语音文字处理自检失败'), (False, '80m 启动失败')]:
        # The second run inherits the prior marker: it must not misdiagnose it.
        (root / 'python_entry.py').write_text(
            "print('VOICE_STARTUP_ERROR: test preflight failure', flush=True)\nraise SystemExit(1)\n"
            if marker else "print('unrelated failure', flush=True)\nraise SystemExit(1)\n")
        result = subprocess.run([sys.executable, str(root / 'supervisor.py'), '--data', str(data),
                                 '--parent', str(os.getpid())], capture_output=True, timeout=15)
        assert result.returncode == 1
        state = json.loads((data / 'runtime.json').read_text())
        assert state['phase'] == 'error' and expected in state['message'], state
    print('PASS: preflight failures identify the voice log; old log markers do not mislabel new failures.')
