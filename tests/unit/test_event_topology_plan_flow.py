"""Static-analysis test: ``event-topology.md`` documents the implemented plan-generation event chain.

The Phase-2.7 Batch 3 documentation update (Steps 10–11, ratified by
ADR-012) requires ``docs/architecture/04-platform/event-topology.md``
"Plan Generation Event Flows → Initial Plan Generation" section to
document the implemented flow:

    twin_model_ready → generate_plan task → training_plan_generated
                   → generate_first_message task → coaching_message_generated

These tests parse the H3 section by regex and assert the four event
names appear in it, and that ``OnboardingService`` is named as the
producer of the chain.
"""

from __future__ import annotations

import pathlib
import re

import pytest

TOPOLOGY = pathlib.Path("docs/architecture/04-platform/event-topology.md")


@pytest.fixture(scope="module")
def topology_text() -> str:
    return TOPOLOGY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def initial_plan_generation_section(topology_text: str) -> str:
    pattern = re.compile(
        r"###\s*Initial Plan Generation\s*\n([\s\S]*?)(?=\n###\s|\Z)",
        re.MULTILINE,
    )
    match = pattern.search(topology_text)
    assert match is not None, (
        "Plan Generation Event Flows → Initial Plan Generation section "
        "not found in event-topology.md"
    )
    return match.group(1)


def test_initial_plan_generation_section_exists(initial_plan_generation_section: str) -> None:
    assert initial_plan_generation_section.strip() != ""


def test_section_documents_twin_model_ready(initial_plan_generation_section: str) -> None:
    assert "twin_model_ready" in initial_plan_generation_section


def test_section_documents_training_plan_generated(initial_plan_generation_section: str) -> None:
    assert "training_plan_generated" in initial_plan_generation_section


def test_section_documents_coaching_message_generated(
    initial_plan_generation_section: str,
) -> None:
    assert "coaching_message_generated" in initial_plan_generation_section


def test_section_names_onboarding_service_as_producer(
    initial_plan_generation_section: str,
) -> None:
    assert "OnboardingService" in initial_plan_generation_section
