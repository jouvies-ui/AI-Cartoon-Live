"""Build an offline x64 Windows installer from audited snapshots and Windows wheels."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
from brand_windows import apply_icon, make_assets
from distribution_audit import validate_inputs, validate_payload, scan_files

ROOT = Path(__file__).resolve().parent
from build_paths import WORK
RELEASE = ROOT / 'release'
VERSION = json.loads((ROOT / 'package.json').read_text())['version']


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def wheel_install(wheel, site):
    with zipfile.ZipFile(wheel) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            parts = Path(item.filename).parts
            if parts[0].endswith('.data'):
                if parts[1] not in ('purelib', 'platlib'):
                    # No console scripts needed: all entry points use python_entry.py.
                    continue
                parts = parts[2:]
            target = site.joinpath(*parts)
            if not target.resolve().is_relative_to(site.resolve()):
                raise ValueError('Invalid wheel path')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(item))


def stage():
    validate_inputs(ROOT)
    make_assets(ROOT)
    validate_inputs(ROOT)
    app = WORK / 'app'
    if app.exists():
        shutil.rmtree(app)
    app.mkdir()
    cache = WORK / 'cache'
    for record in json.loads((cache / 'downloads.json').read_text()):
        assert digest(cache / record['name']) == record['sha256'], record['name']
    with zipfile.ZipFile(cache / 'electron-v45.2.3-win32-x64.zip') as z:
        z.extractall(app)
    (app / 'electron.exe').rename(app / 'WhaleCompanion.exe')
    apply_icon(app / 'WhaleCompanion.exe', ROOT / 'assets/whale.ico')
    if (app / 'LICENSE').exists():
        (app / 'LICENSE').rename(app / 'LICENSE.electron')
    (app / 'resources/default_app.asar').unlink(missing_ok=True)
    target = app / 'resources/app'
    target.mkdir(parents=True)
    names = ('package.json', 'main.cjs', 'preload.cjs', 'shell.html', 'shell.css',
             'shell.js', 'python_entry.py', 'supervisor.py', 'text_normalize.py', 'THIRD-PARTY-NOTICES.txt')
    for name in names:
        shutil.copy2(ROOT / name, target / name)
    shutil.copytree(ROOT / 'assets', target / 'assets')
    # Windows PowerShell 5 interprets non-ASCII script text correctly with BOM.
    (target / 'check-gpu.ps1').write_text((ROOT / 'check-gpu.ps1').read_text(), encoding='utf-8-sig')
    runtime = target / 'runtime'
    with zipfile.ZipFile(cache / 'python-3.12.10-embed-amd64.zip') as z:
        z.extractall(runtime)
    (runtime / 'python312._pth').write_text('python312.zip\n.\nLib/site-packages\nimport site\n')
    site = runtime / 'Lib/site-packages'
    wheels = sorted((WORK / 'wheels').glob('*.whl'))
    assert len(wheels) >= 40, 'Windows wheels are not ready'
    inventory = []
    for wheel in wheels:
        assert wheel.name.endswith(('win_amd64.whl', 'none-any.whl')), wheel.name
        wheel_install(wheel, site)
        inventory.append({'file': wheel.name, 'sha256': digest(wheel)})
    payload = target / 'payload'
    payload.mkdir()
    shutil.copytree(ROOT / 'source/repo', payload / 'repo',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store', '._*'))
    for mode in ('40m', '80m'):
        service = payload / ('hojo-' + mode)
        shutil.copytree(ROOT / 'source' / service.name, service,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'zh1.wav', '._*'))
        manifest = json.loads((service / 'model-manifest.json').read_text())
        models = service / 'models'
        models.mkdir()
        for name, expected in manifest['files'].items():
            original = WORK / 'models' / mode / name
            assert original.stat().st_size == expected['size'] and digest(original) == expected['sha256'], name
            shutil.copy2(original, models / name)
        if mode == '80m':
            optimized = service / 'optimized/int8-v1'
            shutil.copytree(models, optimized)
            source_hash = digest(models / 'Hojo-TTS-Light-llm.onnx')
            graph = WORK / 'models/int8.onnx'
            graph_hash = digest(graph)
            assert graph_hash == 'e96ec82e538841bec82d3c545b3fcee3c6c2b9a4ca1ac45f3465015640ffd14c'
            shutil.copy2(graph, optimized / 'Hojo-TTS-Light-llm.onnx')
            dump(optimized / 'optimization.json', {'source_sha256': source_hash,
                'sha256': graph_hash, 'method': 'ONNX Runtime dynamic INT8 MatMul, CPU only'})
    voice = payload / 'voices/hojo80_demo_zh_f_01'
    voice.mkdir(parents=True)
    shutil.copy2(ROOT / 'source/hojo-80m/zh1.wav', voice / 'reference.wav')
    dump(voice / 'voice.json', {'id': voice.name, 'label': 'Hojo 80M 官方示例女声',
         'transcript': '现在的外卖确实坑多，要不咱换家稍微贵点的？可能品质好点。',
         'audio_sha256': digest(voice / 'reference.wav'), 'language': 'zh', 'gender': 'f',
         'source': 'HojoAI/Hojo-TTS-Light/Hojo-TTS-Light-80M/assets/zh1.wav'})
    dump(payload / 'character-default.json', {'name': '小雅',
         'personality': '温柔、机灵、有一点俏皮的鲸鱼娘。认真听对方说话，记住熟悉的人的偏好；遇到难过的事情先共情，不强行卖萌。',
         'speaking_style': '用自然、简短的中文口语回应当前话题，像熟悉的朋友。普通回答15至25字，最多50字；不反复自我介绍，不把动作或表情说明念出来。',
         'voice_template': 'hojo_zh_f_02', 'expression_strength': .9,
         'auto_gestures': True, 'remember': True, 'memory_turns': 12})
    binaries = payload / 'bin'; binaries.mkdir()
    licenses = payload / 'licenses'; licenses.mkdir()
    with zipfile.ZipFile(cache / 'douyinLive-v2.3.2-3b0c44876c2a-windows-amd64.zip') as z:
        (binaries / 'douyinLive.exe').write_bytes(z.read('douyinLive.exe'))
        for name in ('LICENSE', 'README.md', 'config.example.yaml', 'docs/http-api.md', 'sign/README.md'):
            p = licenses / 'douyinLive' / name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(z.read(name))
    with zipfile.ZipFile(cache / 'imageio_ffmpeg-0.6.0-py3-none-win_amd64.whl') as z:
        exe = next(n for n in z.namelist() if n.endswith('.exe'))
        (binaries / 'ffmpeg.exe').write_bytes(z.read(exe))
        for name in z.namelist():
            if any(x in name.lower() for x in ('license', 'readme')) and not name.endswith('/'):
                p = licenses / 'ffmpeg' / Path(name).name; p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(z.read(name))
    (licenses / 'ffmpeg/SOURCE.txt').write_text(
        'Binary: imageio-ffmpeg 0.6.0 Windows x64 official wheel.\n'
        'Upstream build/source instructions: https://github.com/imageio/imageio-ffmpeg/tree/v0.6.0\n'
        'FFmpeg source: https://ffmpeg.org/download.html\n', encoding='utf-8')
    dump(payload / 'build-provenance.json', {'runtime': json.loads((cache / 'downloads.json').read_text()),
          'windows_wheels': inventory, 'target': 'Windows 10/11 x64', 'version': VERSION})
    # Include corresponding modified source and rebuild scripts with the app.
    source = target / 'build-source'; source.mkdir()
    build_files = ('build.py', 'build_paths.py', 'brand_windows.py', 'distribution_audit.py', 'distribution-files.json',
                   'fetch_models.py', 'fetch_runtime.py', 'quantize_model.py', 'installer.nsi',
                   'requirements-windows.txt', 'requirements-windows.lock', 'requirements-build.txt', 'README.md', 'README.en.md', 'LICENSE', 'NOTICE', 'THIRD-PARTY-NOTICES.txt',
                   'check-gpu.ps1', 'python_entry.py', 'supervisor.py', 'text_normalize.py',
                   'verify_portable.py', 'verify_unicode_startup.py', 'verify_startup_diagnostics.py')
    for name in build_files:
        shutil.copy2(ROOT / name, source / name)
    shutil.copytree(ROOT / 'docs', source / 'docs')
    report = {**validate_inputs(ROOT), **validate_payload(app, ROOT), **scan_files(app)}
    dump(WORK / f'verification-{VERSION}/distribution-audit.json', report)
    files = {str(p.relative_to(app)).replace('\\', '/'): {'size': p.stat().st_size, 'sha256': digest(p)}
             for p in sorted(app.rglob('*')) if p.is_file()}
    dump(target / 'installed-files.json', files)
    print(json.dumps({'files': len(files), 'bytes': sum(v['size'] for v in files.values()), 'app': str(app)}), flush=True)
    return app


def compile_installer(app):
    RELEASE.mkdir(exist_ok=True)
    # Only remove the installed file list; never recursively delete user-chosen directories.
    def quote(value):
        return value.replace('$', '$$').replace('"', '$\\"')
    files = sorted((p for p in app.rglob('*') if p.is_file()), reverse=True)
    folders = sorted((p for p in app.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True)
    delete = WORK / 'uninstall-files.nsh'
    delete.write_text('\n'.join(
        'Delete "$INSTDIR\\' + quote(str(p.relative_to(app)).replace('/', '\\')) + '"' for p in files) + '\n' +
        '\n'.join('RMDir "$INSTDIR\\' + quote(str(p.relative_to(app)).replace('/', '\\')) + '"' for p in folders), encoding='utf-8')
    output = WORK / f'AI-Cartoon-Live-{VERSION}-Windows-x64-Setup.exe'
    values = {'OUTPUT_FILE': output, 'NOTICE_FILE': ROOT / 'THIRD-PARTY-NOTICES.txt',
        'GPU_CHECK': app / 'resources/app/check-gpu.ps1', 'VC_REDIST': WORK / 'cache/vc_redist.x64.exe',
        'APP_DIR': app, 'UNINSTALL_FILES': delete, 'APP_ICON': ROOT / 'assets/whale.ico', 'VERSION': VERSION}
    with (WORK / 'nsis.log').open('w') as log:
        subprocess.run(['makensis', '-V2', *['-D'+k+'='+str(v) for k,v in values.items()],
                        str(ROOT / 'installer.nsi')], check=True, stdout=log, stderr=subprocess.STDOUT)
    staged = RELEASE / (output.name + '.partial')
    shutil.copyfile(output, staged)
    staged.replace(RELEASE / output.name)
    assert digest(RELEASE / output.name) == digest(output)
    (RELEASE / 'SHA256SUMS.txt').write_text(digest(output) + '  ' + output.name + '\n')
    shutil.copy2(app / 'resources/app/installed-files.json', RELEASE / 'installed-files.json')
    print(output, output.stat().st_size, digest(output), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--compile-only', action='store_true')
    parser.add_argument('--stage-only', action='store_true')
    args = parser.parse_args()
    app = WORK / 'app' if args.compile_only else stage()
    if not args.stage_only:
        compile_installer(app)
