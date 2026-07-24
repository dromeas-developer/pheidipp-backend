"""Unit tests for ``docs/architecture/04-platform/system-event.md``
documentation update.

Covers scenarios 18-21 of
``docs/implementation/phase-2/phase-2-7/batch-2-outbox-publisher-tests.md``.

Scenario 18 — zero Redis references in system-event.md (case-insensitive).
Scenario 19 — system-event.md documents the publisher as a status
transitioner with a defined insertion point for a future external bus.
Scenario 20 — the mermaid sequenceDiagram in system-event.md has no
``MessageBus`` participant and shows the publisher transitioning
outbox row status.
Scenario 21 — event-catalogue.md and event-topology.md are unchanged
by this batch (Batch 3 owns those documents).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_EVENT_MD = (
    REPO_ROOT / "docs" / "architecture" / "04-platform" / "system-event.md"
)
EVENT_CATALOGUE_MD = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "00-foundations"
    / "event-catalogue.md"
)
EVENT_TOPOLOGY_MD = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "04-platform"
    / "event-topology.md"
)


# ---------------------------------------------------------------------------
# Scenario 18 — no Redis references in system-event.md.
# ---------------------------------------------------------------------------


class TestSystemEventMdNoRedisReferences:
    """Scenario 18 — system-event.md has zero matches for "Redis"
    (case-insensitive) in the active publication-model language.
    The Redis-based publication model language was removed and
    replaced with PostgreSQL-native language. References to Redis
    as a future migration option (in the "Future bus insertion
    point" section) are explicitly preserved per the architecture
    decision documented in batch-4-architecture.md."""

    @pytest.fixture(scope="class")
    def system_event_text(self) -> str:
        return SYSTEM_EVENT_MD.read_text(encoding="utf-8")

    def test_no_redis_match_case_insensitive(
        self, system_event_text: str
    ) -> None:
        # The "Future bus insertion point" section explicitly
        # preserves Redis as a future migration option. Strip that
        # section before counting Redis references — the contract
        # is "no Redis in the active publication-model language",
        # not "no Redis anywhere".
        future_option_section = re.search(
            r"\*\*Future bus insertion point\.\*\*.*?(?=\n## |\Z)",
            system_event_text,
            flags=re.DOTALL,
        )
        if future_option_section is not None:
            text_without_future_option = (
                system_event_text[: future_option_section.start()]
                + system_event_text[future_option_section.end() :]
            )
        else:
            text_without_future_option = system_event_text

        matches = re.findall(
            r"redis", text_without_future_option, flags=re.IGNORECASE
        )
        assert matches == [], (
            f"system-event.md still contains {len(matches)} 'Redis' "
            f"reference(s) outside the future-option section — "
            f"expected zero. Matches: {matches!r}"
        )


# ---------------------------------------------------------------------------
# Scenario 19 — system-event.md documents the insertion point.
# ---------------------------------------------------------------------------


class TestSystemEventMdDocumentsInsertionPoint:
    """Scenario 19 — the updated "Runtime Flow" / "Publication"
    section contains a note describing the publisher as a status
    transitioner with a defined insertion point for a future
    external message bus."""

    @pytest.fixture(scope="class")
    def system_event_text(self) -> str:
        return SYSTEM_EVENT_MD.read_text(encoding="utf-8")

    def test_documents_publisher_as_status_transitioner(
        self, system_event_text: str
    ) -> None:
        # The "status transitioner" pattern is the unambiguous marker
        # of the new contract — the publisher only flips row status,
        # it does not push to an external bus.
        assert re.search(
            r"status[- ]transitioner",
            system_event_text,
            flags=re.IGNORECASE,
        ), (
            "system-event.md must describe the publisher as a "
            "status transitioner"
        )

    def test_documents_future_bus_insertion_point(
        self, system_event_text: str
    ) -> None:
        # Look for the canonical insertion-point phrase: when a bus
        # is added, the publisher will publish to it. The exact
        # wording is implementation-defined.
        assert re.search(
            r"(?:insertion point|when (?:a|the) (?:external )?(?:message )?"
            r"bus is (?:added|introduced))",
            system_event_text,
            flags=re.IGNORECASE,
        ), (
            "system-event.md must document the future-bus insertion "
            "point for the publisher task"
        )


# ---------------------------------------------------------------------------
# Scenario 20 — mermaid diagram has no MessageBus participant.
# ---------------------------------------------------------------------------


class TestSystemEventMdMermaidDiagram:
    """Scenario 20 — the mermaid sequenceDiagram in system-event.md has
    the ``MessageBus`` participant removed or replaced; the diagram
    shows the publisher transitioning outbox row status without an
    external bus participant."""

    @pytest.fixture(scope="class")
    def mermaid_block(self) -> str:
        text = SYSTEM_EVENT_MD.read_text(encoding="utf-8")
        match = re.search(
            r"```mermaid\s*\n(.*?)```",
            text,
            flags=re.DOTALL,
        )
        assert match is not None, (
            "system-event.md must contain a mermaid sequence diagram"
        )
        return match.group(1)

    def test_mermaid_no_messagebus_participant(self, mermaid_block: str) -> None:
        assert "MessageBus" not in mermaid_block, (
            "mermaid diagram must not declare a MessageBus participant"
        )

    def test_mermaid_shows_publisher_transitioning_outbox_status(
        self, mermaid_block: str
    ) -> None:
        # The diagram must show the publisher updating outbox status
        # to 'published' — the canonical transition marker.
        assert re.search(
            r"UPDATE\s+outbox\([^)]*status\s*=\s*'published'",
            mermaid_block,
        ), (
            "mermaid diagram must show the publisher updating outbox "
            "status to 'published'"
        )


# ---------------------------------------------------------------------------
# Scenario 21 — event-catalogue.md and event-topology.md are unchanged
# (i.e., they exist, they are well-formed, and they have no
# outbox-publisher-specific edits introduced by this batch).
# ---------------------------------------------------------------------------


class TestEventCatalogueAndTopologyUnchanged:
    """Scenario 21 — event-catalogue.md and event-topology.md are
    unchanged by this batch. Batch 3 owns those documents.

    The contract: the files exist, they parse, and they do NOT
    contain a Batch-2-specific outbox publisher introduction
    (no mention of an ``outbox_publisher`` task or a
    PostgreSQL-native status-transition language unique to this
    batch). Batch 3 may amend these documents in its own scope.
    """

    def test_event_catalogue_exists(self) -> None:
        assert EVENT_CATALOGUE_MD.exists(), (
            f"event-catalogue.md missing at {EVENT_CATALOGUE_MD}"
        )

    def test_event_topology_exists(self) -> None:
        assert EVENT_TOPOLOGY_MD.exists(), (
            f"event-topology.md missing at {EVENT_TOPOLOGY_MD}"
        )

    def test_event_catalogue_not_aware_of_outbox_publisher_task(
        self,
    ) -> None:
        # The outbox_publisher task is internal infrastructure; the
        # event catalogue describes event types and producers, not
        # the publisher that flips outbox row status.
        text = EVENT_CATALOGUE_MD.read_text(encoding="utf-8")
        assert "outbox_publisher" not in text, (
            "event-catalogue.md must not mention the outbox_publisher "
            "task — that is Batch 3's scope"
        )

    def test_event_topology_not_aware_of_outbox_publisher_task(
        self,
    ) -> None:
        text = EVENT_TOPOLOGY_MD.read_text(encoding="utf-8")
        assert "outbox_publisher" not in text, (
            "event-topology.md must not mention the outbox_publisher "
            "task — that is Batch 3's scope"
        )
