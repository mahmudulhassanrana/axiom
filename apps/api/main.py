"""
ASGI entry for local runs: ``uvicorn main:app --reload`` (execute from ``apps/api``).

Adds ``src`` to ``sys.path`` so ``axiom_api`` imports work without a prior ``pip install -e``.
Loads ``.env`` from the monorepo root (``../../.env``) then ``apps/api/.env`` so ``DATABASE_URL``
matches ``docker compose`` / root tooling when the API is started only from ``apps/api``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT.parent.parent / ".env")
    load_dotenv(_ROOT / ".env", override=True)
except ImportError:
    pass
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from axiom_api.app import create_app

app = create_app()
