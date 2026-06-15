# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-15

### Added
- **`langgraph-server` adapter** — red-team a LangGraph agent running as an HTTP server
  (`langgraph dev` / LangGraph Platform) over `langgraph_sdk`, without installing
  aion-redteam in the agent's environment. Discovers the server's assistants/graphs and
  runs each scenario in a fresh thread. New CLI flags: `--base-url`, `--assistant`,
  `--api-key`. Ships as the `langgraph-server` extra.
- **Live progress** — `run` now streams each scenario verdict as it completes with a
  progress spinner, instead of appearing frozen during long scans.
- **PDF report** (`PDFReporter`, `pdf` extra) — `run --pdf` / `report --format pdf`.
- **Detailed reports** — HTML and PDF now show, per scenario: description, injection
  point, the attack payload, success criteria (with which matched), the agent's actual
  response (evidence), mitigations, and references.
- `ToolCallJudge` (`tool_call_check` criteria) — assert that an agent invoked a specific
  tool, optionally with given argument substrings. Tool calls are serialized to JSON for
  structured matching. Makes tool-using agents properly testable.
- CLI `--timeout` and `--num-runs` flags on `run` to override per-scenario execution
  budgets — needed for slow, multi-step tool-using agents on local models.

## [0.1.0] - 2026-06-11

### Added
- Core layer: scenario schema + `ScenarioLoader`, `StringMatch`/`Regex` judges, the
  `Target` lifecycle abstraction, the async `Runner` (PASS/FAIL/FLAKY/ERROR/TIMEOUT
  verdicts with a severity-weighted 0–100 risk score), and terminal/JSON/HTML reporters.
- LangGraph adapter (`LangGraphTarget`) with graph discovery and per-injection-point
  message encoding.
- Real example LangGraph agents (Anthropic-backed and a no-key local Ollama target) and
  a quick-start demo script.
- `ollama` optional extra (`langchain-ollama`) for the local example.

### Fixed
- CLI/demo force UTF-8 console output so verdict icons no longer crash on legacy Windows
  code pages (cp1252).

### Security
- Judge evaluation now runs untrusted (community-contributed) regex with a capped input
  length and under the scenario timeout, bounding ReDoS-style hangs.
- Target loading appends (rather than prepends) the target directory to `sys.path` so a
  target cannot shadow stdlib/installed packages; documented the load/scenario trust
  model in `SECURITY.md`.
- CLI (`aion-redteam`): `list`, `validate`, `run`, `report`, `init`.
- Bundled scenario library: 20 scenarios spanning all 10 OWASP Agentic (ASI) categories,
  plus the `owasp_agentic_top10` policy manifest.
- Documentation: scenario authoring and adapter guides; community files (LICENSE,
  SECURITY, CONTRIBUTING, CODE_OF_CONDUCT); GitHub issue templates and CI.

[Unreleased]: https://github.com/Cypharia/aion-redteam/commits/main
