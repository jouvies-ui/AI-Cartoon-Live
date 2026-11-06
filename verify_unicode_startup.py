"""Real WFST regression tests plus a simulated Windows narrow-path boundary.

Run with host Python and wetext==0.2.1 / kaldifst==1.9.0 installed.
This does not claim Windows execution or native GPU/DPAPI verification.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import wetext

ROOT = Path(__file__).resolve().parent
GUARD = '''
import os
from pathlib import Path
import kaldifst
native = kaldifst.TextNormalizer
paths = []
def narrow_reader(path):
    assert path.isascii(), 'simulated narrow reader cannot open Unicode filename'
    assert not Path(path).is_absolute(), 'must use a relative filename'
    paths.append(path)
    return native(path)
kaldifst.TextNormalizer = narrow_reader
'''
SHIM = '''
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import text_normalize
assert Path.cwd() == Path(__file__).parent
cwd = os.getcwd()
samples = ['今天是2026年，完成了50%。', 'Hello, 50 percent.', '<zh_ni3>你好，3个。']
reference = [text_normalize.normalize_text(t) for t in samples]
assert '百分之五十' in reference[0] and '2026' not in reference[0]
assert 'fifty' in reference[1].lower()
assert '<zh_ni3>' in reference[2]
with ThreadPoolExecutor(6) as pool:
    values = list(pool.map(text_normalize.normalize_text, samples * 8))
assert values == reference * 8
assert os.getcwd() == cwd
print(json.dumps({'result': 'passed', 'outputs': reference, 'concurrent_requests': 24}, ensure_ascii=False))
'''


def run(app, mode):
    script = GUARD + '\nimport runpy, sys\nsys.argv = [sys.argv[1], sys.argv[2]]\nrunpy.run_path(sys.argv[0], run_name="__main__")'
    # Start outside the app, as the desktop supervisor does (user data cwd).
    return subprocess.run([sys.executable, '-c', script, str(app / 'python_entry.py'), mode],
                          cwd=app.parents[1], text=True, capture_output=True, timeout=90)


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix='whale-unicode-') as directory:
        app = Path(directory) / '用户资料 🐋' / '鲸鱼娘 安装' / 'resources/app'
        app.mkdir(parents=True)
        for name in ('python_entry.py', 'text_normalize.py'):
            shutil.copy2(ROOT / name, app / name)
        for mode in ('40m', '80m'):
            upstream = ROOT / f'source/hojo-{mode}/upstream/Hojo-TTS-Light-{mode.upper()}/text_normalize.py'
            assert upstream.read_bytes() == (ROOT / 'text_normalize.py').read_bytes()
        shutil.copytree(Path(wetext.__file__).parent, app / 'wetext',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (app / 'uvicorn.py').write_text(textwrap.dedent(SHIM))
        old = subprocess.run([sys.executable, '-c', GUARD + '\nfrom wetext import Normalizer\nNormalizer(lang="zh").normalize("50%")'],
                             cwd=app, text=True, capture_output=True, timeout=90)
        assert old.returncode != 0 and 'simulated narrow reader' in old.stderr, old.stderr
        for mode in ('40m', '80m'):
            result = run(app, mode)
            assert result.returncode == 0, result.stdout + result.stderr
            assert 'VOICE_TEXT_PREFLIGHT_OK: zh/en' in result.stdout
            results.append({'mode': mode, **json.loads(result.stdout.splitlines()[-1])})
        (app / 'wetext/fsts/zh/tn/tagger.fst').unlink()
        missing = run(app, '80m')
        assert missing.returncode != 0
        assert 'VOICE_STARTUP_ERROR:' in missing.stderr and '资源缺失' in missing.stderr
        assert 'VOICE_TEXT_PREFLIGHT_OK' not in missing.stdout
    print(json.dumps({'platform': sys.platform, 'old_unicode_boundary_reproduced': True,
                      'missing_resource_diagnostic': 'passed', 'services': results,
                      'windows_native_tested': False}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
