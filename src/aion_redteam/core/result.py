"""Result models produced by a red-team run.

**Red-team inversion:** "attack succeeded" is *bad* for the agent. So when the attack's
success criteria match, the agent is vulnerable and its verdict is ``FAIL``. When the
agent resists (criteria do not match), the verdict is ``PASS``.
"""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field

from aion_redteam.core.scenario import OwaspCategory, Severity


class Verdict(enum.StrEnum):
    """Outcome of a scenario after all repetitions."""

    PASS = "PASS"  # agent resisted: attack never succeeded
    FAIL = "FAIL"  # agent vulnerable: attack succeeded often enough
    FLAKY = "FLAKY"  # attack succeeded sometimes (below the flaky threshold)
    ERROR = "ERROR"  # the agent/run threw an exception
    TIMEOUT = "TIMEOUT"  # the run exceeded its time budget


class SingleRunDetail(BaseModel):
    """Record of one execution of a scenario (one of ``num_runs`` repetitions)."""

    run_index: int
    attack_succeeded: bool
    matched_criteria: list[int] = Field(default_factory=list)
    agent_response: str = ""
    error: str | None = None
    timed_out: bool = False
    duration_ms: int = 0


class ScenarioResult(BaseModel):
    """Aggregated result for a single scenario across all its repetitions."""

    scenario_id: str
    scenario_name: str
    owasp_category: OwaspCategory
    severity: Severity
    verdict: Verdict
    success_rate: float  # fraction of runs where the attack succeeded (0.0–1.0)
    num_runs: int
    run_details: list[SingleRunDetail] = Field(default_factory=list)
    duration_ms: int = 0

    @property
    def success_count(self) -> int:
        """Number of runs in which the attack succeeded."""
        return sum(1 for r in self.run_details if r.attack_succeeded)


class CategorySummary(BaseModel):
    """Per-OWASP-category roll-up of verdicts."""

    category: OwaspCategory
    total: int = 0
    passed: int = 0
    failed: int = 0
    flaky: int = 0
    errors: int = 0
    timeouts: int = 0


class RunResult(BaseModel):
    """The full result of a red-team run: every scenario plus roll-ups."""

    target_name: str
    adapter: str
    timestamp: datetime = Field(default_factory=datetime.now)
    total_scenarios: int = 0
    passed: int = 0
    failed: int = 0
    flaky: int = 0
    errors: int = 0
    timeouts: int = 0
    risk_score: int = 0  # 0–100, derived from severities of failed scenarios
    scenario_results: list[ScenarioResult] = Field(default_factory=list)
    by_category: dict[str, CategorySummary] = Field(default_factory=dict)
