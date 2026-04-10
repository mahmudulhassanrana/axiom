"""ASGI entrypoint: ``uvicorn axiom_api.main:app`` (requires ``src`` on PYTHONPATH or editable install)."""

from __future__ import annotations

import sys
from pathlib import Path

# Running from source without ``pip install -e``: ensure ``src`` is importable.
_src = Path(__file__).resolve().parents[1]
if _src.name == "src" and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from axiom_api.app import create_app

app = create_app()
