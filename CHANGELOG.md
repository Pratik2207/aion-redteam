# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
