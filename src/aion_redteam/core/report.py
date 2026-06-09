"""Reporters: turn a :class:`RunResult` into terminal, JSON, or HTML output.

The report is first-class output — the screenshot for the thread, the appendix for the
blog post, the evidence for a CVE. All three formats render the same data.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, select_autoescape
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from aion_redteam.core.result import RunResult, ScenarioResult, Verdict
from aion_redteam.core.scenario import OWASP_CATEGORY_NAMES, OwaspCategory

# Verdict → (icon, rich colour) for terminal rendering.
_VERDICT_STYLE: dict[Verdict, tuple[str, str]] = {
    Verdict.PASS: ("✅", "green"),
    Verdict.FAIL: ("❌", "red"),
    Verdict.FLAKY: ("⚠️", "yellow"),
    Verdict.ERROR: ("💥", "magenta"),
    Verdict.TIMEOUT: ("⏱", "blue"),
}


def risk_band(score: int) -> str:
    """Map a 0–100 risk score to a qualitative band."""
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


class TerminalReporter:
    """Renders a colored PASS/FAIL summary to the terminal using ``rich``."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize with an optional pre-configured ``rich`` console."""
        self.console = console or Console()

    def render(self, result: RunResult) -> None:
        """Print the full report for a run to the console."""
        self.console.print(
            "\n[bold]aion-redteam[/bold] — OWASP Agentic Security Testing"
        )
        self.console.print(
            f"Target: [cyan]{result.target_name}[/cyan] ({result.adapter})"
        )
        self.console.print(
            f"Scenarios: {result.total_scenarios} loaded\n"
        )

        for category in self._categories_in_result(result):
            self._render_category(result, category)

        self._render_summary(result)

    def _categories_in_result(self, result: RunResult) -> list[OwaspCategory]:
        """Return the OWASP categories present in the result, in canonical order."""
        present = {r.owasp_category for r in result.scenario_results}
        return [c for c in OwaspCategory if c in present]

    def _render_category(self, result: RunResult, category: OwaspCategory) -> None:
        """Print one category heading and its scenario rows."""
        name = OWASP_CATEGORY_NAMES[category]
        self.console.print(f" [bold]{category.value}[/bold] {name}")
        rows = [r for r in result.scenario_results if r.owasp_category == category]
        for r in sorted(rows, key=lambda x: x.scenario_id):
            self._render_row(r)
        self.console.print()

    def _render_row(self, r: ScenarioResult) -> None:
        """Print a single scenario result line."""
        icon, color = _VERDICT_STYLE[r.verdict]
        succeeded = r.success_count
        line = Text()
        line.append(f"  {icon} ")
        line.append(f"{r.scenario_id} ", style="bold")
        line.append(f"{r.scenario_name:<42.42} ")
        line.append(f"{r.verdict.value:<7}", style=color)
        line.append(f" ({succeeded}/{r.num_runs} succeeded)", style="dim")
        self.console.print(line)

    def _render_summary(self, result: RunResult) -> None:
        """Print the closing summary panel with the risk score."""
        band = risk_band(result.risk_score)
        band_color = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red", "CRITICAL": "red"}[
            band
        ]
        summary = (
            f"[green]{result.passed} PASS[/green] │ "
            f"[red]{result.failed} FAIL[/red] │ "
            f"[yellow]{result.flaky} FLAKY[/yellow] │ "
            f"[magenta]{result.errors} ERROR[/magenta] │ "
            f"[blue]{result.timeouts} TIMEOUT[/blue]\n"
            f"Overall Risk Score: [bold {band_color}]{result.risk_score}/100 ({band})[/]"
        )
        self.console.print(Panel(summary, title="Results", expand=False))


class JSONReporter:
    """Serializes a run to machine-readable JSON for CI/CD integration."""

    def render(self, result: RunResult) -> str:
        """Return the run as indented JSON."""
        return result.model_dump_json(indent=2)

    def write(self, result: RunResult, path: Path | str) -> Path:
        """Write the JSON report to ``path`` and return it."""
        out = Path(path)
        out.write_text(self.render(result), encoding="utf-8")
        return out


class HTMLReporter:
    """Renders a single-page HTML report via Jinja2."""

    def __init__(self) -> None:
        """Build the Jinja2 environment with autoescaping enabled."""
        self._env = Environment(autoescape=select_autoescape(["html"]))
        self._template = self._env.from_string(_HTML_TEMPLATE)

    def render(self, result: RunResult) -> str:
        """Return the report as an HTML string."""
        return self._template.render(
            result=result,
            band=risk_band(result.risk_score),
            category_names=OWASP_CATEGORY_NAMES,
            verdict_icon={v: icon for v, (icon, _) in _VERDICT_STYLE.items()},
        )

    def write(self, result: RunResult, path: Path | str) -> Path:
        """Write the HTML report to ``path`` and return it."""
        out = Path(path)
        out.write_text(self.render(result), encoding="utf-8")
        return out


_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>aion-redteam report — {{ result.target_name }}</title>
<style>
  :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --fg:#e6edf3; --muted:#8b949e; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }
  .wrap { max-width:960px; margin:0 auto; padding:32px 20px; }
  h1 { margin:0 0 4px; font-size:24px; }
  .sub { color:var(--muted); margin-bottom:24px; }
  .score { display:flex; gap:24px; align-items:center; background:var(--card);
           border:1px solid var(--border); border-radius:12px; padding:20px 24px; margin-bottom:24px; }
  .score .num { font-size:44px; font-weight:700; }
  .band-LOW { color:#3fb950; } .band-MEDIUM { color:#d29922; }
  .band-HIGH { color:#f85149; } .band-CRITICAL { color:#f85149; }
  .chips span { display:inline-block; padding:4px 10px; border-radius:999px; margin:2px;
                font-size:13px; background:#21262d; }
  .PASS { color:#3fb950; } .FAIL { color:#f85149; } .FLAKY { color:#d29922; }
  .ERROR { color:#bc8cff; } .TIMEOUT { color:#58a6ff; }
  table { width:100%; border-collapse:collapse; background:var(--card);
          border:1px solid var(--border); border-radius:12px; overflow:hidden; margin-bottom:24px; }
  th,td { text-align:left; padding:10px 14px; border-bottom:1px solid var(--border); font-size:14px; }
  th { color:var(--muted); font-weight:600; }
  details { background:var(--card); border:1px solid var(--border); border-radius:10px;
            padding:10px 16px; margin-bottom:10px; }
  summary { cursor:pointer; font-weight:600; }
  .meta { color:var(--muted); font-size:13px; margin:6px 0; }
  .mit { background:#21262d; border-radius:8px; padding:8px 12px; margin-top:8px; font-size:13px; }
  code { background:#21262d; padding:1px 5px; border-radius:4px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>aion-redteam report</h1>
  <div class="sub">Target: <code>{{ result.target_name }}</code> &middot;
    adapter <code>{{ result.adapter }}</code> &middot;
    {{ result.timestamp.strftime('%Y-%m-%d %H:%M') }}</div>

  <div class="score">
    <div>
      <div class="num band-{{ band }}">{{ result.risk_score }}<span style="font-size:18px">/100</span></div>
      <div class="band-{{ band }}">{{ band }} RISK</div>
    </div>
    <div class="chips">
      <span class="PASS">{{ result.passed }} PASS</span>
      <span class="FAIL">{{ result.failed }} FAIL</span>
      <span class="FLAKY">{{ result.flaky }} FLAKY</span>
      <span class="ERROR">{{ result.errors }} ERROR</span>
      <span class="TIMEOUT">{{ result.timeouts }} TIMEOUT</span>
      <span>{{ result.total_scenarios }} total</span>
    </div>
  </div>

  <table>
    <tr><th>Category</th><th>Total</th><th>Pass</th><th>Fail</th><th>Flaky</th><th>Error</th><th>Timeout</th></tr>
    {% for cat, s in result.by_category.items() %}
    <tr>
      <td>{{ cat }} {{ category_names[cat] }}</td>
      <td>{{ s.total }}</td><td class="PASS">{{ s.passed }}</td>
      <td class="FAIL">{{ s.failed }}</td><td class="FLAKY">{{ s.flaky }}</td>
      <td class="ERROR">{{ s.errors }}</td><td class="TIMEOUT">{{ s.timeouts }}</td>
    </tr>
    {% endfor %}
  </table>

  <h2>Scenarios</h2>
  {% for r in result.scenario_results %}
  <details>
    <summary>
      {{ verdict_icon[r.verdict] }}
      <span class="{{ r.verdict.value }}">{{ r.verdict.value }}</span>
      &nbsp;{{ r.scenario_id }} — {{ r.scenario_name }}
    </summary>
    <div class="meta">Category {{ r.owasp_category }} &middot; severity {{ r.severity }}
      &middot; attack succeeded {{ r.success_count }}/{{ r.num_runs }}
      &middot; {{ r.duration_ms }} ms</div>
  </details>
  {% endfor %}

  <p class="meta">Generated by aion-redteam. Fix findings with
    <a href="https://github.com/Cypharia/aion-guard" style="color:#58a6ff">aion-guard</a>.</p>
</div>
</body>
</html>
"""
