"""Configurable build cache; independent of any developer workstation."""
import os
from pathlib import Path
import tempfile

WORK = Path(os.environ.get('AI_CARTOON_BUILD_DIR', str(Path(tempfile.gettempdir()) / 'ai-cartoon-live-build'))).expanduser().resolve()
