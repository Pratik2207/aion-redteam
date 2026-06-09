"""Tests that the bundled scenario library is complete and internally consistent."""

from __future__ import annotations

from aion_redteam.core.scenario import (
    OwaspCategory,
    ScenarioLoader,
    bundled_scenarios_dir,
)


def _load_bundled():
    return ScenarioLoader(bundled_scenarios_dir()).load_all()


def test_bundled_scenarios_load() -> None:
    scenarios = _load_bundled()
    assert len(scenarios) >= 20


def test_two_scenarios_per_category() -> None:
    scenarios = _load_bundled()
    by_cat: dict[OwaspCategory, int] = {}
    for s in scenarios:
        by_cat[s.owasp_category] = by_cat.get(s.owasp_category, 0) + 1
    for category in OwaspCategory:
        assert by_cat.get(category, 0) >= 2, f"{category} has fewer than 2 scenarios"


def test_scenario_ids_unique() -> None:
    ids = [s.id for s in _load_bundled()]
    assert len(ids) == len(set(ids)), "duplicate scenario ids found"


def test_every_scenario_has_mitigations() -> None:
    # Mitigations are how we point users at aion-guard; every scenario must have them.
    for s in _load_bundled():
        assert s.mitigations, f"{s.id} is missing mitigations"
