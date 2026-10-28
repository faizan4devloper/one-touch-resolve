"""Pytest bootstrap: make the ``src/`` package root importable.

Keeps test imports clean (``from agent...``, ``from channels...``, ``from shared...``)
after the source packages were consolidated under ``src/``.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
