"""Unit tests for alembic/env.py wiring.

Covers the side fix in Phase 1-7 Batch 1: env.py must reference
``settings.DATABASE_URL`` (the existing Settings field) and must
not reference the non-existent ``settings.POSTGRES_DSN``. The
side fix was flagged by the architect resolution report and is a
one-line change in a file already in scope of the procrastinate
migration.
"""

from __future__ import annotations

from pathlib import Path


_ALEMBIC_ENV_PATH = Path("alembic/env.py")


class TestAlembicEnv:
    def test_env_py_references_settings_database_url(self) -> None:
        assert _ALEMBIC_ENV_PATH.exists()
        source = _ALEMBIC_ENV_PATH.read_text(encoding="utf-8")
        assert "settings.DATABASE_URL" in source

    def test_env_py_does_not_reference_postgres_dsn(self) -> None:
        source = _ALEMBIC_ENV_PATH.read_text(encoding="utf-8")
        assert "POSTGRES_DSN" not in source
