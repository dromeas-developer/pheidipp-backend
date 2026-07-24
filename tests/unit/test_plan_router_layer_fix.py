"""Static-analysis test: plan router delegates to PlanQueryService, no direct SQL.

The Phase-2.7 Batch 3 plan-router layer fix (G-07) requires that
``app/api/v1/plan.py`` no longer execute SQLAlchemy queries directly.
All read queries previously inlined in the route handlers are now
delegated to ``PlanQueryService``.

These tests assert the negative — that the forbidden substrings
``session.execute(`` and ``select(`` are absent from the file. A
literal-text scan is sufficient because the file does not import
``sqlalchemy`` or any module that would alias those names, so any
occurrence of the substrings would be a real violation.
"""

from __future__ import annotations

import pathlib

import pytest

PLAN_PY = pathlib.Path("app/api/v1/plan.py")


@pytest.fixture(scope="module")
def plan_source() -> str:
    return PLAN_PY.read_text(encoding="utf-8")


def test_plan_router_does_not_call_session_execute(plan_source: str) -> None:
    assert "session.execute(" not in plan_source


def test_plan_router_does_not_construct_select_statements(plan_source: str) -> None:
    assert "select(" not in plan_source


def test_plan_router_does_not_import_sqlalchemy(plan_source: str) -> None:
    assert "sqlalchemy" not in plan_source
