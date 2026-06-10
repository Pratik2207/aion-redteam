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

## Testing your own agent

aion-redteam is **not tied to any LLM provider.** The harness never calls a model itself —
it invokes *your* compiled LangGraph graph, and whatever model your graph uses (OpenAI,
Anthropic, Gemini, or a **local Ollama** model) is what gets red-teamed. The only
credentials you need are the ones your agent already needs to run; a local Ollama agent
needs **no API key at all**.

Three steps:

1. **Expose a compiled graph.** In your agent file, make the compiled `StateGraph`
   available as a module-level variable named `graph` (also accepted: `app`, `agent`,
   `workflow`, or a `build_graph()` factory). Use the `MessagesState` convention.
2. **Install aion-redteam into the same environment** as your agent (so its imports
   resolve): `uv pip install -e ".[langgraph]"` (plus your agent's own deps).
3. **Run it:**
   ```bash
   aion-redteam run --target path/to/your_agent.py --adapter langgraph --html report.html
   ```
   If your compiled graph has a non-standard name, pass `--attribute my_graph`.

### Local Ollama example

A complete, no-key, fully local target lives at
[`examples/ollama_langgraph_agent.py`](examples/ollama_langgraph_agent.py) (uses
`langchain-ollama` + `ChatOllama`):

```bash
uv pip install -e ".[langgraph,ollama]"
ollama pull llama3.2
aion-redteam run --target examples/ollama_langgraph_agent.py --adapter langgraph --category ASI01
```

> **Windows note:** if you hit an `OPENSSL_Uplink ... no OPENSSL_Applink` crash, a
> standalone Python on your PATH is colliding with another OpenSSL DLL. Build the venv on
> a system/Anaconda Python instead: `uv venv aion-redteam --python C:\path\to\python.exe`.

## License

MIT — the offensive tool stays free forever. See [LICENSE](LICENSE).
