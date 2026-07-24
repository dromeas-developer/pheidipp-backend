"""Unit tests for the ``outbox_publisher`` procrastinate task registration.

Covers scenarios 16-17 of
``docs/implementation/phase-2/phase-2-7/batch-2-outbox-publisher-tests.md``.

The tests introspect the procrastinate ``App`` task registry
(``app.worker.app.app.tasks``) to verify the publisher is registered
under its expected name, and inspect the function source to verify
the periodic schedule interval falls in the 10-30 seconds band.
"""

from __future__ import annotations

import importlib
import inspect
import re
from collections.abc import Callable



# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _worker_module():
    """Import the worker module fresh so the @app.task decorators run."""
    return importlib.import_module("app.worker.app")


def _extract_decorator_source(func: Callable[..., object]) -> str:
    """Return the source text of *func* including its decorators.

    ``inspect.getsource`` returns only the function body; the
    ``@app.periodic`` and ``@app.task`` decorators live one level
    above. Walking back to the enclosing module source gives us
    the full decorator block.
    """
    module = inspect.getmodule(func)
    assert module is not None
    module_source = inspect.getsource(module)
    # Match the function definition with its decorators.
    pattern = (
        r"(@app\.[^\n]+(?:\n[^\n]+)*?\n)?"
        r"(@app\.[^\n]+(?:\n[^\n]+)*?\n)?"
        rf"async def {func.__name__}\("
    )
    match = re.search(pattern, module_source)
    assert match is not None, (
        f"Could not locate {func.__name__} decorators in module source"
    )
    return module_source[match.start():match.end()]


# ---------------------------------------------------------------------------
# Test: task registration (scenario 16).
# ---------------------------------------------------------------------------


class TestOutboxPublisherRegistered:
    """Scenario 16 — outbox_publisher is registered in the procrastinate
    App's task registry under its expected name."""

    def test_outbox_publisher_in_task_registry(self) -> None:
        worker = _worker_module()
        assert "outbox_publisher" in worker.app.tasks

    def test_outbox_publisher_task_named_correctly(self) -> None:
        worker = _worker_module()
        task = worker.app.tasks["outbox_publisher"]
        assert task.name == "outbox_publisher"

    def test_outbox_publisher_callable(self) -> None:
        worker = _worker_module()
        task = worker.app.tasks["outbox_publisher"]
        assert callable(task)


# ---------------------------------------------------------------------------
# Test: schedule interval (scenario 17).
# ---------------------------------------------------------------------------


class TestOutboxPublisherScheduleInterval:
    """Scenario 17 — the periodic schedule interval is between 10 and
    30 seconds. The exact value is implementation-defined within this
    band. The current implementation uses ``*/15 * * * * *`` (15 s)."""

    def test_periodic_decorator_present(self) -> None:
        worker = _worker_module()
        decorator_block = _extract_decorator_source(worker.outbox_publisher)
        assert "@app.periodic" in decorator_block

    def test_periodic_cron_in_ten_to_thirty_seconds_band(self) -> None:
        worker = _worker_module()
        decorator_block = _extract_decorator_source(worker.outbox_publisher)
        cron_match = re.search(
            r'@app\.periodic\(\s*cron\s*=\s*"([^"]+)"\s*\)',
            decorator_block,
        )
        assert cron_match is not None, (
            "Could not locate @app.periodic(cron=...) decorator on "
            "outbox_publisher"
        )
        cron_expr = cron_match.group(1)
        # 6-field cron: seconds minutes hours day-of-month month day-of-week
        fields = cron_expr.split()
        assert len(fields) == 6, (
            f"Expected 6-field cron (with seconds), got {cron_expr!r}"
        )
        seconds_field = fields[0]
        # Acceptable forms: "*/10", "*/15", "*/20", "*/25", "*/30",
        # and step values like "10", "15", "20", "25", "30" (literal
        # seconds). The contract is between 10 and 30 seconds.
        step_match = re.fullmatch(
            r"(?:\*/)?(\d+)(?:/(\d+))?",
            seconds_field,
        )
        assert step_match is not None, (
            f"Seconds field {seconds_field!r} is not a step expression"
        )
        # First captured group is the step or the literal value.
        interval = int(step_match.group(1))
        assert 10 <= interval <= 30, (
            f"Publisher interval {interval}s is outside the 10-30s band"
        )
