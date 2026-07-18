"""Pure helpers for SQLAlchemy declarative schema introspection.

No database engine is created at import time.
"""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine, inspect


def get_sync_database_url() -> str:
    """Return a synchronous psycopg2 DATABASE_URL from the environment."""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )
    return database_url


def _inspect_method(method_name: str, table: str) -> list[dict[str, Any]]:
    """Generic sync-engine inspect helper."""
    engine = create_engine(get_sync_database_url())
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            method = getattr(inspector, method_name)
            return list(method(table))
    finally:
        engine.dispose()


def db_columns(table: str) -> list[dict[str, Any]]:
    """Return column metadata for a table."""
    return _inspect_method("get_columns", table)


def db_unique_constraints(table: str) -> list[dict[str, Any]]:
    """Return unique constraint metadata for a table."""
    return _inspect_method("get_unique_constraints", table)


def db_check_constraints(table: str) -> list[dict[str, Any]]:
    """Return check constraint metadata for a table."""
    return _inspect_method("get_check_constraints", table)


def db_indexes(table: str) -> list[dict[str, Any]]:
    """Return index metadata for a table."""
    return _inspect_method("get_indexes", table)


def db_foreign_keys(table: str) -> list[dict[str, Any]]:
    """Return foreign key metadata for a table."""
    return _inspect_method("get_foreign_keys", table)
