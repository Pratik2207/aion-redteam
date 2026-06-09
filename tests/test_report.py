"""Smoke tests for the reporters."""

from __future__ import annotations

import json

from rich.console import Console

from aion_redteam.core.report import (
    HTMLReporter,
    JSONReporter,
    TerminalReporter,
    risk_band,
)
from aion_redteam.core.result import (
    RunResult,
    ScenarioResult,
    SingleRunDetail,
    Verdict,
)
from aion_redteam.core.scenario import OwaspCategory, Severity


def _sample_run() -> RunResult:
    sr = ScenarioResult(
        scenario_id="ASI01-001",
        scenario_name="role play hijack",
        owasp_category=OwaspCategory.ASI01,
        severity=Severity.HIGH,
        verdict=Verdict.FAIL,
        success_rate=1.0,
        num_runs=2,
        run_details=[
            SingleRunDetail(run_index=0, attack_succeeded=True),
            SingleRunDetail(run_index=1, attack_succeeded=True),
        ],
        mitigations=["Use aion-guard with the persona_lock policy"],
    )
    return RunResult(
        target_name="demo_agent.py",
        adapter="langgraph",
        total_scenarios=1,
        failed=1,
        risk_score=15,
        scenario_results=[sr],
    )


def test_risk_band_thresholds() -> None:
    assert risk_band(0) == "LOW"
    assert risk_band(24) == "LOW"
    assert risk_band(25) == "MEDIUM"
    assert risk_band(50) == "HIGH"
    assert risk_band(80) == "CRITICAL"


def test_json_reporter_roundtrips() -> None:
    out = JSONReporter().render(_sample_run())
    data = json.loads(out)
    assert data["risk_score"] == 15
    assert data["scenario_results"][0]["verdict"] == "FAIL"


def test_html_reporter_contains_key_fields() -> None:
    html = HTMLReporter().render(_sample_run())
    assert "<!doctype html>" in html
    assert "ASI01-001" in html
    assert "15" in html
    assert "role play hijack" in html
    assert "persona_lock" in html  # mitigations shown for failed scenarios


def test_terminal_reporter_runs() -> None:
    # Render to a recording console; just assert it produces output without error.
    console = Console(record=True, width=100)
    TerminalReporter(console).render(_sample_run())
    text = console.export_text()
    assert "ASI01-001" in text
    assert "FAIL" in text
