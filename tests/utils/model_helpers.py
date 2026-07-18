"""Pure helpers for ORM mapper introspection (no DB required)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import CheckConstraint, Table, UniqueConstraint

if TYPE_CHECKING:
    from sqlalchemy import Column, ForeignKey, Index
    from sqlalchemy.orm import DeclarativeBase


def get_columns(model: type[DeclarativeBase]) -> dict[str, Column[Any]]:
    """Return a dict of column.key -> Column for a model.

    ``Table.columns`` is typed by SQLAlchemy as yielding
    ``KeyedColumnElement[Any]`` rather than ``Column[Any]``, but at
    runtime every element is a full ``Column`` instance.  We cast here
    so callers can safely access ``Column``-specific attributes such as
    ``primary_key``, ``nullable``, and ``unique`` without type-checker
    friction.
    """
    return cast(
        "dict[str, Column[Any]]",
        {column.key: column for column in model.__table__.columns},
    )


def get_indexes(model: type[DeclarativeBase]) -> dict[str, Index]:
    """Return a dict of index.name -> Index for a model."""
    table = cast("Table", model.__table__)
    return cast(
        "dict[str, Index]",
        {idx.name: idx for idx in table.indexes},
    )


def get_check_constraints(model: type[DeclarativeBase]) -> list[CheckConstraint]:
    """Return a list of CheckConstraint for a model."""
    table = cast("Table", model.__table__)
    return [c for c in table.constraints if isinstance(c, CheckConstraint)]


def get_unique_constraints(model: type[DeclarativeBase]) -> list[UniqueConstraint]:
    """Return a list of UniqueConstraint for a model."""
    table = cast("Table", model.__table__)
    return [c for c in table.constraints if isinstance(c, UniqueConstraint)]


def get_foreign_keys_referencing(
    model: type[DeclarativeBase], column_key: str
) -> list[ForeignKey]:
    """Return foreign keys referencing a specific column."""
    table = cast("Table", model.__table__)
    return [
        fk for fk in table.foreign_keys if fk.parent.name == column_key
    ]


def get_check_text(check: CheckConstraint) -> str:
    """Unwrap a CheckConstraint's text expression."""
    expr = getattr(check, "expression", None) or getattr(check, "sqltext", None)
    return str(expr) if expr is not None else ""


def get_server_default_text(column: Column[Any]) -> str:
    """Return the server_default argument as a string.

    SQLAlchemy's ``Column.server_default`` is typed as
    ``FetchedValue | None``, but at runtime it is a
    ``DefaultClause`` / ``ColumnDefault``, both of which expose
    ``.arg``. This helper normalises to ``str`` so tests can
    assert on default values without type-checker friction.

    Returns ``""`` when the column has no server default.
    """
    from sqlalchemy.schema import DefaultClause

    default = column.server_default
    if default is None:
        return ""
    # DefaultClause / ColumnDefault store the raw value in .arg.
    # FetchedValue (the base) does not.
    if isinstance(default, DefaultClause):
        return str(default.arg)
    arg = getattr(default, "arg", None)
    return str(arg) if arg is not None else str(default)


def has_column(model: type[DeclarativeBase], name: str) -> bool:
    """Return True if the model has a column with the given name."""
    return any(column.key == name for column in model.__table__.columns)


def get_enum_values(column: Column[Any], enum_cls: type) -> list[str]:
    """Return the list of value names for a SQLAlchemy Enum column.

    Safely extracts enum values from a column that has been narrowed
    to an :class:`~sqlalchemy.Enum` type. Returns an empty list when
    the column is not an Enum or when ``values_callable`` is not set.
    """
    from sqlalchemy import Enum as SAEnum

    if not isinstance(column.type, SAEnum):
        return []
    vc = column.type.values_callable
    if vc is None:
        return []
    return list(vc(enum_cls))
