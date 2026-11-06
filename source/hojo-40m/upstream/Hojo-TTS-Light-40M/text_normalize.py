"""WeText normalization with ASCII relative filenames for Windows kaldifst.

The launcher sets the TTS process cwd once, before importing any worker modules,
to resources/app. Never change cwd while serving requests. Python uses Unicode
Windows APIs for cwd; kaldifst's narrow file reader receives ASCII descendants.
This does not depend on the user name, TEMP, administrator rights or 8.3 names.
"""
from functools import lru_cache
from importlib.resources import files
import os
from pathlib import Path
import re
import threading

_models = {}
_lock = threading.Lock()
_pinyin = re.compile(r'(<zh_[^<>]+>)')
_loader_ready = False


@lru_cache(maxsize=None)
def _load_fst(fst_path):
    from kaldifst import TextNormalizer
    path = Path(files('wetext').joinpath('fsts', fst_path))
    if not path.is_file():
        raise RuntimeError(f'文字处理资源缺失：{path.name}，请重新安装。')
    try:
        relative = os.path.relpath(path, Path.cwd())
        if os.name == 'nt' and not relative.isascii():
            raise ValueError('TTS must start in the packaged resources/app directory')
        return TextNormalizer(relative)
    except Exception as exc:
        raise RuntimeError(f'文字处理资源无法读取：{path.name}，请打开语音日志。') from exc


def _install_loader():
    global _loader_ready
    if not _loader_ready:
        import wetext.constants
        # _LazyFsts looks up this function at call time, before any graph loads.
        wetext.constants.load_fst = _load_fst
        _loader_ready = True


def normalize_text(text, *, language='auto'):
    raw = '' if text is None else str(text).strip()
    if not raw:
        return raw
    lang = ('zh' if re.search(r'[\u4e00-\u9fff]', raw) else 'en') if language == 'auto' else language
    if lang not in ('zh', 'en'):
        raise ValueError('Expected auto, zh or en')
    with _lock:
        _install_loader()
        if lang not in _models:
            from wetext import Normalizer
            _models[lang] = Normalizer(lang=lang, operator='tn', remove_erhua=False)
        normalizer = _models[lang]
        return ''.join(part if _pinyin.fullmatch(part) else normalizer.normalize(part)
                       for part in _pinyin.split(raw) if part)


def preflight():
    """Fail before loading ONNX models, and warm both supported languages."""
    for text in ('今天是2026年，完成了50%。', 'Hello, 50 percent.'):
        if not normalize_text(text):
            raise RuntimeError('文字处理自检没有输出，请重新安装。')
