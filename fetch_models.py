"""Download pinned upstream models; never read private voice directories."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent
from build_paths import WORK
DEST = WORK / 'models'


def fetch(job):
    path, url, expected = job
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temp = path.with_suffix('.part')
        with urllib.request.urlopen(url, timeout=120) as response, temp.open('wb') as output:
            while data := response.read(1024 * 1024):
                output.write(data)
        temp.replace(path)
    assert path.stat().st_size == expected['size'], path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected['sha256'], path
    print(path.name, 'verified', flush=True)


if __name__ == '__main__':
    jobs = []
    for variant, repo in [('40m', 'HojoAI/Hojo-TTS-Light-40M'), ('80m', 'HojoAI/Hojo-TTS-Light')]:
        manifest = json.loads((ROOT / 'source' / ('hojo-' + variant) / 'model-manifest.json').read_text())
        for name, expected in manifest['files'].items():
            url = f'https://huggingface.co/{repo}/resolve/{manifest["model_revision"]}/{name}'
            jobs.append((DEST / variant / name, url, expected))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(fetch, jobs))
