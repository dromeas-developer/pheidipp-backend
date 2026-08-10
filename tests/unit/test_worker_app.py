"""Unit tests for the procrastinate worker app wiring.

Covers the connector swap from Psycopg2Connector (sync, psycopg2) to
PsycopgConnector (async, psycopg3) per ADR-014. The unit boundary
here is the module-level ``procrastinate.App(...)`` construction at
``app/worker/app.py``: importing the module already builds the app,
so these tests only need to assert the connector's type and the
construction keyword used (conninfo= in 3.x; 2.x used dsn=).
"""

from __future__ import annotations

from typing import Any, cast

from app.worker.app import app as procrastinate_app
from app.config import get_procrastinate_dsn
from procrastinate import PsycopgConnector
from procrastinate.contrib.psycopg2 import Psycopg2Connector


class TestWorkerAppConnector:
    def test_app_connector_is_psycopg_connector(self) -> None:
        assert isinstance(procrastinate_app.connector, PsycopgConnector)

    def test_app_does_not_use_psycopg2_connector(self) -> None:
        assert not isinstance(procrastinate_app.connector, Psycopg2Connector)

    def test_app_connector_uses_conninfo_keyword(self) -> None:
        # PsycopgConnector 3.x packs its **kwargs into `_pool_args` and
        # forwards them to the pool factory at open_async() time, so
        # the DSN is stored at `_pool_args["conninfo"]`, not at a
        # public `conninfo` attribute. Its presence there proves the
        # 3.x constructor keyword was used.
        connector = cast(PsycopgConnector, procrastinate_app.connector)
        assert connector._pool_args["conninfo"] is not None

    def test_app_connector_receives_get_procrastinate_dsn(self) -> None:
        # get_procrastinate_dsn() strips the `+driver` suffix from
        # PROCRASTINATE_DATABASE_URL, producing a libpq-format DSN
        # that PsycopgConnector accepts. Equality with the connector's
        # stored conninfo proves the helper (not raw settings) was
        # passed to the constructor.
        connector = cast(PsycopgConnector, procrastinate_app.connector)
        assert (
            connector._pool_args["conninfo"]
            == get_procrastinate_dsn()
        )


class TestWorkerAppTaskRegistration:
    def test_signal_clean_task_is_registered(self) -> None:
        tasks = cast("dict[str, Any]", procrastinate_app.tasks)
        assert "signal_clean" in tasks

    def test_threshold_detection_task_is_registered(self) -> None:
        tasks = cast("dict[str, Any]", procrastinate_app.tasks)
        assert "threshold_detection" in tasks

    def test_generate_plan_task_is_registered(self) -> None:
        tasks = cast("dict[str, Any]", procrastinate_app.tasks)
        assert "generate_plan" in tasks

    def test_generate_first_message_task_is_registered(self) -> None:
        tasks = cast("dict[str, Any]", procrastinate_app.tasks)
        assert "generate_first_message" in tasks
