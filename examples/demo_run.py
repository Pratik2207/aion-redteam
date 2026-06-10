"""Quick-start demo: red-team the real example agent against bundled scenarios.

This runs the genuine LangGraph + Anthropic agent (a real model call per run), so it
requires an API key:

    pip install "aion-redteam[langgraph,llm-judge]"
    export ANTHROPIC_API_KEY=sk-ant-...
    python examples/demo_run.py

It runs one scenario per OWASP category (fast) and writes an HTML report.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from pathlib import Path

from aion_redteam.adapters.langgraph import LangGraphTarget
from aion_redteam.core.report import HTMLReporter, TerminalReporter
from aion_redteam.core.scenario import ScenarioLoader, bundled_scenarios_dir

HERE = Path(__file__).resolve().parent
EXAMPLE_AGENT = HERE / "simple_langgraph_agent.py"


async def main() -> int:
    # Force UTF-8 console output so verdict icons don't crash on legacy Windows code pages.
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY to run the demo against the real agent.")
        return 1

    # One scenario per category keeps the demo quick; drop the [:1] slicing to run all.
    all_scenarios = ScenarioLoader(bundled_scenarios_dir()).load_all()
    seen: set[str] = set()
    selection = []
    for s in all_scenarios:
        if s.owasp_category not in seen and not s.attack.multi_turn:
            seen.add(s.owasp_category)
            # Trim repetitions so the demo is fast and cheap.
            s.execution.num_runs = 2
            selection.append(s)

    target = LangGraphTarget()
    await target.load({"target": str(EXAMPLE_AGENT)})

    from aion_redteam.core.runner import Runner

    result = await Runner(target, selection).run(EXAMPLE_AGENT.name, "langgraph")

    TerminalReporter().render(result)
    out = HTMLReporter().write(result, HERE / "demo-report.html")
    print(f"\nHTML report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
