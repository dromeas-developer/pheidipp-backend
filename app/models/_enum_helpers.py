"""Typed helpers for SQLAlchemy enum columns.

Replaces bare ``values_callable=lambda x: [e.value for e in x]`` with a
properly-typed function so basedpyright strict-mode does not flag the
lambda as having unknown types.
"""

from __future__ import annotations

from enum import Enum


def enum_str_values(enum_cls: type[Enum]) -> list[str]:
    """Return the ``.value`` strings of every member of *enum_cls*.

    Used as ``values_callable`` argument to ``SAEnum`` columns::

        values_callable=enum_str_values,
    """
    return [e.value for e in enum_cls]
