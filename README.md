# aion-redteam

> **Break your agents before attackers do.**

An OWASP-aligned adversarial red-team harness for **LangGraph**, CrewAI, and MCP agents.

`aion-redteam` is a **test framework for adversarial scenarios** — like `pytest`, but the tests
are attacks against AI agents. It is *not* a vulnerability scanner and *not* a fuzzer. It is a
structured, repeatable, OWASP-categorized harness that runs named attack scenarios against real
agent targets and produces `PASS` / `FAIL` / `FLAKY` verdicts with publishable reports.

> Scenarios run against **real agents making real LLM calls** — not mocks or canned data.

## Status

🚧 Early development (v0.1.0, pre-release). Built in phases — see the build plan in `Claude.md`.

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

```bash
# List available scenarios
aion-redteam list

# Run scenarios against a real agent target
aion-redteam run --target examples/simple_langgraph_agent.py --adapter langgraph

# Generate an HTML report from the last run
aion-redteam report --format html --output ./redteam-report.html
```

_(CLI commands land in Phase 4.)_

## License

MIT — the offensive tool stays free forever. See [LICENSE](LICENSE).
