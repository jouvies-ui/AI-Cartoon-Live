"""Disposable reference encodings bound to source audio and encoder weights."""
import hashlib
import os
from pathlib import Path
import tempfile
import zipfile

import numpy as np


class ReferenceCache:
    def __init__(self, directory, encoder_identity):
        self.directory = Path(directory)
        self.identity = encoder_identity

    def key(self, kind, audio_path):
        audio_hash = hashlib.sha256(Path(audio_path).read_bytes()).hexdigest()
        return hashlib.sha256(f'v1:{self.identity}:{kind}:{audio_hash}'.encode()).hexdigest()

    @staticmethod
    def valid(kind, array):
        if kind == 'codec':
            return (array.dtype == np.int64 and array.ndim == 1 and 0 < array.size < 10000
                    and array.min() >= 0 and array.max() < 65536)
        return (kind == 'speaker' and array.dtype == np.float32 and array.ndim == 2
                and array.shape[0] == 1 and 32 <= array.size <= 4096 and np.isfinite(array).all())

    def load(self, key, kind):
        try:
            path = self.directory / (key + '.npz')
            if path.stat().st_size > 1_000_000:
                return None
            with np.load(path, allow_pickle=False) as data:
                value = data['value']
                if (data['key'].item() != key or not self.valid(kind, value)
                        or data['sha256'].item() != hashlib.sha256(value.tobytes()).hexdigest()):
                    return None
                return value
        except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile):
            return None

    def save(self, key, kind, value):
        if not self.valid(kind, value):
            return
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.NamedTemporaryFile(dir=self.directory, suffix='.tmp', delete=False) as handle:
                temporary = Path(handle.name)
                np.savez(handle, value=value, key=np.array(key),
                         sha256=np.array(hashlib.sha256(value.tobytes()).hexdigest()))
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.directory / (key + '.npz'))
        except OSError:
            # A full or read-only cache disk must not break speech synthesis.
            pass
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
