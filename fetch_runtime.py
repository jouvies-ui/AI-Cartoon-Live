"""Fetch official Windows artifacts and retain provenance plus SHA256."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

from build_paths import WORK
CACHE = WORK / 'cache'
CACHE.mkdir(parents=True, exist_ok=True)


def download(name, url, expected=None):
    path = CACHE / name
    if not path.exists():
        temporary = path.with_suffix('.part')
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        temporary.replace(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected and digest != expected:
        raise RuntimeError(f'Checksum mismatch: {name}')
    print(name, path.stat().st_size, flush=True)
    return {'name': name, 'url': url, 'sha256': digest, 'bytes': path.stat().st_size,
            'published_checksum_verified': bool(expected)}


def checksums(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return {line.split()[-1].lstrip('*'): line.split()[0] for line in r.read().decode().splitlines() if line.strip()}


if __name__ == '__main__':
    electron_base = 'https://github.com/electron/electron/releases/download/v45.2.3/'
    collector_base = 'https://github.com/jwwsjlm/douyinLive/releases/download/v2.3.2/'
    electron = 'electron-v45.2.3-win32-x64.zip'
    collector = 'douyinLive-v2.3.2-3b0c44876c2a-windows-amd64.zip'
    e = checksums(electron_base + 'SHASUMS256.txt')
    c = checksums(collector_base + 'douyinLive-v2.3.2-3b0c44876c2a-checksums.txt')
    with urllib.request.urlopen('https://pypi.org/pypi/imageio-ffmpeg/0.6.0/json') as r:
        wheel = next(v for v in json.load(r)['urls'] if v['filename'].endswith('win_amd64.whl'))
    jobs = [(electron, electron_base + electron, e[electron]),
            (collector, collector_base + collector, c[collector]),
            ('python-3.12.10-embed-amd64.zip', 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip', None),
            ('vc_redist.x64.exe', 'https://aka.ms/vs/17/release/vc_redist.x64.exe', None),
            (wheel['filename'], wheel['url'], wheel['digests']['sha256'])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        result = list(pool.map(lambda job: download(*job), jobs))
    (CACHE / 'downloads.json').write_text(json.dumps(result, indent=2))
