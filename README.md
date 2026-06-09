# aion-redteam

> **Break your agents before attackers do.**

An OWASP-aligned adversarial red-team harness for **LangGraph**, CrewAI, and MCP agents.

`aion-redteam` is a **test framework for adversarial scenarios** — like `pytest`, but the tests
are attacks against AI agents. It is *not* a vulnerability scanner and *not* a fuzzer. It is a
structured, repeatable, OWASP-categorized harness that runs named attack scenarios against real
agent targets and produces `PASS` / `FAIL` / `FLAKY` verdicts with publishable reports.

> Scenarios run against **real agents making real LLM calls** — not mocks or canned data.

## Status

🚧 Early development (v0.1.0, pre-release). Working today: the core harness, the LangGraph
adapter, a real example agent, the CLI (`list`/`validate`/`run`/`report`/`init`), and 20
bundled OWASP scenarios. See `Claude.md` for the roadmap.

## OWASP Agentic Top 10 (ASI) — 2026

| ID | Name |
|----|------|
| ASI01 | Agent Goal Hijack |
| ASI02 | Tool Misuse & Exploitation |
| ASI03 | Agent Identity & Privilege Abuse |
| ASI04 | Agentic Supply Chain Compromise |
| ASI05 | Unexpected Code Execution |
| ASI06 | Memory & Context Poisoning |
| ASI07 | Insecure Inter-Agent Communication |
| ASI08 | Cascading Agent Failures |
| ASI09 | Human-Agent Trust Exploitation |
| ASI10 | Rogue Agents |

## Installation (development)

This project uses [`uv`](https://docs.astral.sh/uv/).

```bash
# Create the project virtualenv
uv venv aion-redteam

# Activate it
#   Windows (PowerShell):  aion-redteam\Scripts\Activate.ps1
#   macOS/Linux:           source aion-redteam/bin/activate

# Install the package with dev + langgraph extras (editable)
uv pip install -e ".[dev,langgraph]"
```

## Quickstart

Scenarios run against a **real** agent, so set an API key for the example agent first:

```bash
export ANTHROPIC_API_KEY=sk-ant-...     # the example agent calls a real model
```

```bash
# List available scenarios (no key needed)
aion-redteam list
aion-redteam list --category ASI01

# Validate scenario YAML
aion-redteam validate src/aion_redteam/scenarios

# Run scenarios against a real agent target
aion-redteam run --target examples/simple_langgraph_agent.py --adapter langgraph
aion-redteam run --target examples/simple_langgraph_agent.py --category ASI01 --html report.html

# Regenerate a report from the last run
aion-redteam report --format html --output ./redteam-report.html

# Or run the bundled demo (one scenario per category)
python examples/demo_run.py
```

`run` exits non-zero when the agent is found vulnerable (FAIL or FLAKY), so it gates CI.

## License

MIT — the offensive tool stays free forever. See [LICENSE](LICENSE).
