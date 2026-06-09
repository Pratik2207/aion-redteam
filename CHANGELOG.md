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
- A real Anthropic-backed example LangGraph agent and a quick-start demo script.
- CLI (`aion-redteam`): `list`, `validate`, `run`, `report`, `init`.
- Bundled scenario library: 20 scenarios spanning all 10 OWASP Agentic (ASI) categories,
  plus the `owasp_agentic_top10` policy manifest.
- Documentation: scenario authoring and adapter guides; community files (LICENSE,
  SECURITY, CONTRIBUTING, CODE_OF_CONDUCT); GitHub issue templates and CI.

[Unreleased]: https://github.com/Cypharia/aion-redteam/commits/main
