# Contributing to aion-redteam

Thanks for helping break agents before attackers do. The most valuable contribution is
usually a **new, well-crafted scenario**.

## Development setup

This project uses [`uv`](https://docs.astral.sh/uv/).

```bash
uv venv aion-redteam
#   Windows (PowerShell):  aion-redteam\Scripts\Activate.ps1
#   macOS/Linux:           source aion-redteam/bin/activate
uv pip install -e ".[dev,langgraph]"
```

## Before you open a PR

```bash
ruff check src tests examples      # lint
ruff format src tests examples     # format (optional but appreciated)
pytest -q                          # tests must pass
aion-redteam validate src/aion_redteam/scenarios/   # if you touched scenarios
```

The real-agent end-to-end test (`tests/test_realagent_e2e.py`) is skipped automatically
unless `ANTHROPIC_API_KEY` is set, so you don't need a key to run the suite.

## Adding a scenario

See [docs/scenario_authoring.md](docs/scenario_authoring.md). Checklist:

- [ ] Correct `owasp_category` and matching `id` prefix.
- [ ] Realistic payload; unambiguous success criteria (canary tokens encouraged).
- [ ] At least one `mitigations` entry.
- [ ] `aion-redteam validate` passes.

## Adding an adapter

See [docs/adapter_guide.md](docs/adapter_guide.md). Adapters must drive the **real**
agent; only adapter-plumbing unit tests may use deterministic stand-ins.

## Commit and PR conventions

- **Conventional commits**: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`.
- **Atomic commits** — one logical change each. No 2,000-line "initial commit" dumps.
- **Branch per feature**: `feat/<thing>`, `fix/<thing>`. Open a PR even when solo.
- CI must be green before merge.

## Code style

- Type hints on all function signatures and return types.
- Google-style docstrings on public classes and functions.
- `pathlib.Path`, never `os.path`. `pydantic.BaseModel`, never `@dataclass`.
- No `print()` in library code (the CLI uses `rich`).

By contributing you agree your contributions are licensed under the project's MIT license.
