"""Static-analysis test: ``event-catalogue.md`` names ``OnboardingService`` as the ``twin_model_ready`` producer.

The Phase-2.7 Batch 3 documentation update (Step 11, ratified by
ADR-012) requires the ``twin_model_ready`` entry in
``docs/architecture/00-foundations/event-catalogue.md`` to name
``OnboardingService`` as the producer — the producer semantic that
the shipped code implements (the bootstrap TwinState insert fires
``twin_model_ready`` for all tiers).

These tests parse the H3 section by regex and assert the producer is
``OnboardingService``. The consumer description is also asserted to
mention the plan-generation path (the test does not require the
literal string "generate_plan procrastinate task" — the catalogue
may name the service or the task body).
"""

from __future__ import annotations

import pathlib
import re

import pytest

CATALOGUE = pathlib.Path("docs/architecture/00-foundations/event-catalogue.md")


@pytest.fixture(scope="module")
def catalogue_text() -> str:
    return CATALOGUE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def twin_model_ready_section(catalogue_text: str) -> str:
    pattern = re.compile(
        r"###\s*`twin_model_ready`\s*\n([\s\S]*?)(?=\n###\s|\Z)",
        re.MULTILINE,
    )
    match = pattern.search(catalogue_text)
    assert match is not None, (
        "`twin_model_ready` section not found in event-catalogue.md"
    )
    return match.group(1)


def test_twin_model_ready_section_exists(twin_model_ready_section: str) -> None:
    assert twin_model_ready_section.strip() != ""


def test_producer_is_onboarding_service(twin_model_ready_section: str) -> None:
    assert "**Producer:**" in twin_model_ready_section
    assert "OnboardingService" in twin_model_ready_section


def test_consumer_is_plan_generation_path(twin_model_ready_section: str) -> None:
    """The consumer description must reference the plan-generation path.

    The catalogue may name ``PlanGenerationService`` (the service the
    ``generate_plan`` worker task invokes) or the literal task name.
    Either is acceptable — the test asserts the wiring is documented,
    not the specific wording.
    """
    lowered = twin_model_ready_section.lower()
    assert (
        "plangenerationservice" in lowered
        or "generate_plan" in lowered
        or "plan generation" in lowered
    )
