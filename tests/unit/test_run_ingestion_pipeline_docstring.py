"""Static-analysis test: ``run_ingestion_pipeline`` docstring accurately describes event publication.

The Phase-2.7 Batch 3 cleanup (closing G-09) requires the
``ActivityIngestionService.run_ingestion_pipeline`` docstring to
state that the method publishes ``sport_type_detected``,
``activity_ingested``, and ``activity_calibration_eligible`` events
via ``EventPublisher`` within the transaction. The old docstring
incorrectly stated that the method "Does NOT publish events".

This test reads the docstring at runtime via ``inspect.getdoc`` —
the same accessor the production code would use — and asserts the
required substrings are present and the denial phrase is absent.
"""

from __future__ import annotations

import inspect

import pytest

from app.services.activity_ingestion_service import ActivityIngestionService


@pytest.fixture(scope="module")
def docstring() -> str:
    doc = inspect.getdoc(ActivityIngestionService.run_ingestion_pipeline)
    assert doc is not None, "run_ingestion_pipeline has no docstring"
    return doc


def test_docstring_names_sport_type_detected(docstring: str) -> None:
    assert "sport_type_detected" in docstring


def test_docstring_names_activity_ingested(docstring: str) -> None:
    assert "activity_ingested" in docstring


def test_docstring_names_activity_calibration_eligible(docstring: str) -> None:
    assert "activity_calibration_eligible" in docstring


def test_docstring_references_event_publisher(docstring: str) -> None:
    assert "EventPublisher" in docstring


def test_docstring_references_transactional_outbox(docstring: str) -> None:
    assert "transactional outbox" in docstring


def test_docstring_states_in_caller_transaction(docstring: str) -> None:
    assert "within the caller's transaction" in docstring


def test_docstring_no_longer_denies_event_publication(docstring: str) -> None:
    assert "Does NOT" not in docstring
    assert "does not publish" not in docstring.lower()
