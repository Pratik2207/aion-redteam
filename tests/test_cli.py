"""Smoke tests for the Typer CLI (no real agent required)."""

from __future__ import annotations

from typer.testing import CliRunner

from aion_redteam.cli.main import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "aion-redteam" in result.stdout


def test_list_bundled() -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "ASI01-001" in result.stdout


def test_list_category_filter() -> None:
    result = runner.invoke(app, ["list", "--category", "ASI05"])
    assert result.exit_code == 0
    assert "ASI05-001" in result.stdout
    assert "ASI01-001" not in result.stdout


def test_validate_bundled(tmp_path) -> None:
    from aion_redteam.core.scenario import bundled_scenarios_dir

    result = runner.invoke(app, ["validate", str(bundled_scenarios_dir())])
    assert result.exit_code == 0
    assert "valid" in result.stdout


def test_run_help_exposes_overrides() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--timeout" in result.stdout
    assert "--num-runs" in result.stdout


def test_run_rejects_unknown_adapter(tmp_path) -> None:
    fake = tmp_path / "agent.py"
    fake.write_text("graph = None\n", encoding="utf-8")
    result = runner.invoke(app, ["run", "--target", str(fake), "--adapter", "nope"])
    assert result.exit_code == 2


def test_init_detects_langgraph(tmp_path) -> None:
    agent = tmp_path / "my_agent.py"
    agent.write_text("from langgraph.graph import StateGraph\n", encoding="utf-8")
    out = tmp_path / "redteam_config.yaml"
    result = runner.invoke(app, ["init", str(agent), "--output", str(out)])
    assert result.exit_code == 0
    assert out.is_file()
    assert "langgraph" in out.read_text(encoding="utf-8")
