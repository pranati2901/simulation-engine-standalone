"""Test setup — point the app at a throwaway SQLite DB before it is imported."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_db = Path(tempfile.gettempdir()) / "goalcert_test.db"
if _db.exists():
    _db.unlink()
os.environ["GOALCERT_DATABASE_URL"] = f"sqlite+pysqlite:///{_db.as_posix()}"
os.environ["GOALCERT_SEED_ON_STARTUP"] = "true"
