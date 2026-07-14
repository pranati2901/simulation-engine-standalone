"""SQLAlchemy engine/session setup. Stub — wire in once persistence replaces the
in-memory dicts in services/run_manager.py and scenarios/loader.py.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from ..core.settings import settings

# check_same_thread is a sqlite-only pysqlite option — passing it under Postgres
# (psycopg) raises a TypeError, so it's only applied when database_url is sqlite.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()