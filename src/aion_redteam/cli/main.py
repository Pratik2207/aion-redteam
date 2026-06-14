"""The ``aion-redteam`` command-line interface (built with Typer).

Commands:
    list      List bundled (or custom) scenarios, with category/severity filters.
    validate  Parse and validate scenario YAML files, reporting actionable errors.
    run       Execute scenarios against a real agent target and report verdicts.
    report    Regenerate an HTML/JSON report from a saved results JSON file.
    init      Inspect an agent file, detect its framework, and write a config stub.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from aion_redteam import __version__
from aion_redteam.adapters import available_adapters, get_adapter
from aion_redteam.core.report import HTMLReporter, JSONReporter, TerminalReporter
from aion_redteam.core.result import RunResult
from aion_redteam.core.runner import Runner
from aion_redteam.core.scenario import (
    OWASP_CATEGORY_NAMES,
    Scenario,
    ScenarioLoader,
    ScenarioLoadError,
    Severity,
    bundled_scenarios_dir,
)
from aion_redteam.core.target import TargetError


def _force_utf8_streams() -> None:
    """Force UTF-8 console output with a safe fallback.

    Verdict icons and box-drawing characters are non-ASCII; legacy Windows code
    pages (e.g. cp1252) raise UnicodeEncodeError on them. This keeps the CLI from
    crashing while printing a report.
    """
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


_force_utf8_streams()

app = typer.Typer(
    name="aion-redteam",
    help="OWASP-aligned adversarial red-team harness for AI agents.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)

# Default location for the most recent run's JSON, used by `report` and `run --save`.
_LAST_RUN = Path(".aion_redteam") / "last_run.json"


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"aion-redteam {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """aion-redteam — break your agents before attackers do."""


def _load_scenarios(scenarios_path: Path | None) -> list[Scenario]:
    """Load scenarios from a path (or the bundled set), exiting on load errors."""
    root = scenarios_path or bundled_scenarios_dir()
    try:
        return ScenarioLoader(root).load_all()
    except ScenarioLoadError as exc:
        err_console.print(f"[red]Scenario error[/red] {exc}")
        raise typer.Exit(code=2) from exc


def _filter_scenarios(
    scenarios: list[Scenario],
    category: str | None,
    severity: Severity | None,
    scenario_id: str | None,
) -> list[Scenario]:
    """Apply --category / --severity / --scenario filters."""
    result = scenarios
    if category:
        result = [s for s in result if s.owasp_category.value == category.upper()]
    if severity:
        result = [s for s in result if s.severity == severity]
    if scenario_id:
        result = [s for s in result if s.id == scenario_id]
    return result


@app.command("list")
def list_scenarios(
    scenarios: Path | None = typer.Option(
        None, "--scenarios", help="Scenario directory (defaults to bundled set)."
    ),
    category: str | None = typer.Option(
        None, "--category", help="Filter by OWASP category, e.g. ASI01."
    ),
    severity: Severity | None = typer.Option(
        None, "--severity", help="Filter by severity."
    ),
) -> None:
    """List available scenarios."""
    loaded = _filter_scenarios(_load_scenarios(scenarios), category, severity, None)
    if not loaded:
        console.print("[yellow]No scenarios match the given filters.[/yellow]")
        raise typer.Exit()

    table = Table(title=f"{len(loaded)} scenarios")
    table.add_column("ID", style="bold cyan")
    table.add_column("Category")
    table.add_column("Severity")
    table.add_column("Difficulty")
    table.add_column("Name")
    for s in loaded:
        table.add_row(
            s.id,
            f"{s.owasp_category.value} {OWASP_CATEGORY_NAMES[s.owasp_category]}",
            _severity_markup(s.severity),
            s.difficulty.value,
            s.name,
        )
    console.print(table)


@app.command("validate")
def validate(
    path: Path = typer.Argument(..., help="Scenario file or directory to validate."),
) -> None:
    """Validate scenario YAML files against the schema."""
    loader = ScenarioLoader(path)
    files = loader.discover()
    if not files:
        err_console.print(f"[yellow]No scenario files found under {path}.[/yellow]")
        raise typer.Exit(code=1)

    errors = 0
    for f in files:
        try:
            loader.load_file(f)
            console.print(f"[green]OK[/green]   {f}")
        except ScenarioLoadError as exc:
            errors += 1
            console.print(f"[red]FAIL[/red] {f}\n      {exc.message}")
    console.print(f"\n{len(files) - errors}/{len(files)} valid.")
    if errors:
        raise typer.Exit(code=1)


@app.command("run")
def run(
    target: Path = typer.Option(..., "--target", help="Path to the agent file."),
    adapter: str = typer.Option("langgraph", "--adapter", help="Framework adapter."),
    scenarios: Path | None = typer.Option(
        None, "--scenarios", help="Scenario directory (defaults to bundled set)."
    ),
    category: str | None = typer.Option(None, "--category", help="Filter by category."),
    severity: Severity | None = typer.Option(None, "--severity", help="Filter by severity."),
    scenario_id: str | None = typer.Option(
        None, "--scenario", help="Run only this scenario id."
    ),
    attribute: str | None = typer.Option(
        None, "--attribute", help="Name of the compiled graph/agent in the target file."
    ),
    timeout: float | None = typer.Option(
        None, "--timeout", help="Override per-scenario timeout in seconds "
        "(useful for slow tool-using agents on local models).",
    ),
    num_runs: int | None = typer.Option(
        None, "--num-runs", help="Override the repetitions per scenario.",
    ),
    html_out: Path | None = typer.Option(
        None, "--html", help="Also write an HTML report to this path."
    ),
    json_out: Path | None = typer.Option(
        None, "--json", help="Also write a JSON report to this path."
    ),
) -> None:
    """Run scenarios against a real agent target."""
    if adapter not in available_adapters():
        err_console.print(
            f"[red]Unknown adapter[/red] {adapter!r}. Available: "
            f"{', '.join(available_adapters())}"
        )
        raise typer.Exit(code=2)

    selected = _filter_scenarios(
        _load_scenarios(scenarios), category, severity, scenario_id
    )
    if not selected:
        err_console.print("[yellow]No scenarios match the given filters.[/yellow]")
        raise typer.Exit(code=1)

    try:
        result = asyncio.run(
            _execute(target, adapter, attribute, selected, timeout, num_runs)
        )
    except TargetError as exc:
        err_console.print(f"[red]Target error[/red] {exc}")
        raise typer.Exit(code=2) from exc

    TerminalReporter(console).render(result)
    _save_json(result, _LAST_RUN, announce=False)
    if json_out:
        JSONReporter().write(result, json_out)
        console.print(f"JSON report: {json_out}")
    if html_out:
        HTMLReporter().write(result, html_out)
        console.print(f"HTML report: {html_out}")

    # Exit non-zero when the agent is vulnerable, so CI gates on findings.
    if result.failed or result.flaky:
        raise typer.Exit(code=1)


@app.command("report")
def report(
    input_json: Path = typer.Option(
        _LAST_RUN, "--input", help="Saved results JSON (defaults to last run)."
    ),
    fmt: str = typer.Option("html", "--format", help="Output format: html or json."),
    output: Path | None = typer.Option(None, "--output", help="Output file path."),
) -> None:
    """Regenerate a report from a saved results JSON file."""
    if not input_json.is_file():
        err_console.print(f"[red]No results file at[/red] {input_json}. Run a scan first.")
        raise typer.Exit(code=2)
    result = RunResult.model_validate_json(input_json.read_text(encoding="utf-8"))

    if fmt == "json":
        out = output or Path("results.json")
        JSONReporter().write(result, out)
    elif fmt == "html":
        out = output or Path("redteam-report.html")
        HTMLReporter().write(result, out)
    else:
        err_console.print(f"[red]Unknown format[/red] {fmt!r}. Use 'html' or 'json'.")
        raise typer.Exit(code=2)
    console.print(f"Report written: {out}")


@app.command("init")
def init(
    agent: Path = typer.Argument(..., help="Path to the agent Python file."),
    output: Path = typer.Option(
        Path("redteam_config.yaml"), "--output", help="Config file to write."
    ),
) -> None:
    """Detect an agent's framework and write a starter redteam_config.yaml."""
    if not agent.is_file():
        err_console.print(f"[red]File not found:[/red] {agent}")
        raise typer.Exit(code=2)
    detected = _detect_framework(agent)
    config = (
        f"# aion-redteam configuration\n"
        f"target: {agent.as_posix()}\n"
        f"adapter: {detected or 'langgraph'}\n"
        f"# attribute: graph   # set if your compiled graph has a non-standard name\n"
        f"scenarios: null       # null = use the bundled OWASP scenario set\n"
    )
    output.write_text(config, encoding="utf-8")
    detected_msg = detected or "none detected (defaulting to langgraph)"
    console.print(f"Framework: [cyan]{detected_msg}[/cyan]")
    console.print(f"Wrote [green]{output}[/green]")


# -- helpers -----------------------------------------------------------------------


async def _execute(
    target: Path,
    adapter: str,
    attribute: str | None,
    scenarios: list[Scenario],
    timeout: float | None = None,
    num_runs: int | None = None,
) -> RunResult:
    """Load the adapter + target and run the selected scenarios."""
    tgt = get_adapter(adapter)
    config: dict[str, object] = {"target": str(target)}
    if attribute:
        config["attribute"] = attribute
    await tgt.load(config)
    runner = Runner(
        tgt, scenarios, timeout_override=timeout, num_runs_override=num_runs
    )
    return await runner.run(target_name=target.name, adapter=adapter)


def _save_json(result: RunResult, path: Path, announce: bool) -> None:
    """Persist a run's JSON to ``path``, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    JSONReporter().write(result, path)
    if announce:
        console.print(f"Saved results: {path}")


def _detect_framework(agent: Path) -> str | None:
    """Best-effort framework detection by scanning imports in the agent file."""
    text = agent.read_text(encoding="utf-8", errors="ignore")
    if "langgraph" in text or "langchain" in text:
        return "langgraph"
    if "crewai" in text:
        return "crewai"
    if "mcp" in text:
        return "mcp"
    return None


def _severity_markup(severity: Severity) -> str:
    """Colorize a severity label for the terminal."""
    color = {
        Severity.LOW: "green",
        Severity.MEDIUM: "yellow",
        Severity.HIGH: "red",
        Severity.CRITICAL: "bold red",
    }[severity]
    return f"[{color}]{severity.value}[/{color}]"


if __name__ == "__main__":
    app()
