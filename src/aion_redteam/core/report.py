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
        """Print the full report for a run to the console (non-streaming)."""
        self.print_intro(result.target_name, result.adapter, result.total_scenarios)
        prev: OwaspCategory | None = None
        for r in result.scenario_results:
            self.print_scenario(r, prev)
            prev = r.owasp_category
        self.console.print()
        self.print_summary(result)

    def print_intro(self, target_name: str, adapter: str, total: int) -> None:
        """Print the report header (target + scenario count)."""
        self.console.print(
            "\n[bold]aion-redteam[/bold] — OWASP Agentic Security Testing"
        )
        self.console.print(f"Target: [cyan]{target_name}[/cyan] ({adapter})")
        self.console.print(f"Scenarios: {total} loaded\n")

    def print_scenario(self, r: ScenarioResult, prev_category: OwaspCategory | None) -> None:
        """Print a scenario row, emitting the category heading when it changes.

        Designed for live streaming: pass the previous scenario's category as
        ``prev_category`` so headings appear once per category.
        """
        if r.owasp_category != prev_category:
            if prev_category is not None:
                self.console.print()
            name = OWASP_CATEGORY_NAMES[r.owasp_category]
            self.console.print(f" [bold]{r.owasp_category.value}[/bold] {name}")
        self._render_row(r)

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

    def print_summary(self, result: RunResult) -> None:
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


def _san(text: str, limit: int | None = None) -> str:
    """Sanitize text for the PDF's latin-1 core fonts (replace unencodable chars)."""
    if limit is not None and len(text) > limit:
        text = text[:limit] + " …[truncated]"
    return text.encode("latin-1", "replace").decode("latin-1")


# Verdict → RGB colour for the PDF.
_PDF_VERDICT_RGB: dict[str, tuple[int, int, int]] = {
    "PASS": (45, 164, 78),
    "FAIL": (215, 58, 73),
    "FLAKY": (191, 135, 0),
    "ERROR": (130, 80, 223),
    "TIMEOUT": (47, 129, 247),
}


class PDFReporter:
    """Renders a detailed, human-readable PDF report via ``fpdf2``.

    Install with ``pip install "aion-redteam[pdf]"``.
    """

    def render(self, result: RunResult) -> bytes:
        """Return the report as PDF bytes."""
        try:
            from fpdf import FPDF
        except ImportError as exc:  # pragma: no cover - exercised via extras
            raise RuntimeError(
                'PDF reports require fpdf2. Install with: pip install "aion-redteam[pdf]"'
            ) from exc

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        self._header(pdf, result)
        self._summary(pdf, result)
        self._category_table(pdf, result)
        for r in result.scenario_results:
            self._scenario(pdf, r)
        return bytes(pdf.output())

    def write(self, result: RunResult, path: Path | str) -> Path:
        """Write the PDF report to ``path`` and return it."""
        out = Path(path)
        out.write_bytes(self.render(result))
        return out

    # -- sections --------------------------------------------------------------

    def _header(self, pdf: object, result: RunResult) -> None:
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 10, "aion-redteam report", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(110, 110, 110)
        ts = result.timestamp.strftime("%Y-%m-%d %H:%M")
        pdf.cell(
            0, 6,
            _san(f"Target: {result.target_name}  |  adapter: {result.adapter}  |  {ts}"),
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    def _summary(self, pdf: object, result: RunResult) -> None:
        band = risk_band(result.risk_score)
        rgb = {"LOW": (45, 164, 78), "MEDIUM": (191, 135, 0),
               "HIGH": (215, 58, 73), "CRITICAL": (215, 58, 73)}[band]
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*rgb)
        pdf.cell(0, 9, f"Risk score: {result.risk_score}/100 ({band})",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(
            0, 7,
            _san(f"{result.passed} PASS  |  {result.failed} FAIL  |  "
                 f"{result.flaky} FLAKY  |  {result.errors} ERROR  |  "
                 f"{result.timeouts} TIMEOUT  |  {result.total_scenarios} total"),
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.ln(3)

    def _category_table(self, pdf: object, result: RunResult) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "By category", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for cat, s in result.by_category.items():
            name = OWASP_CATEGORY_NAMES.get(OwaspCategory(cat), cat)
            pdf.cell(
                0, 6,
                _san(f"  {cat} {name}: {s.passed} pass / {s.failed} fail / "
                     f"{s.flaky} flaky / {s.errors} err / {s.timeouts} timeout"),
                new_x="LMARGIN", new_y="NEXT",
            )
        pdf.ln(3)

    def _scenario(self, pdf: object, r: ScenarioResult) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*_PDF_VERDICT_RGB.get(r.verdict.value, (0, 0, 0)))
        pdf.multi_cell(
            0, 7,
            _san(f"[{r.verdict.value}] {r.scenario_id} - {r.scenario_name}"),
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.set_text_color(90, 90, 90)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(
            0, 5,
            _san(f"{r.owasp_category} {OWASP_CATEGORY_NAMES.get(r.owasp_category, '')}"
                 f"  |  severity {r.severity}  |  difficulty {r.difficulty}"
                 f"  |  attack succeeded {r.success_count}/{r.num_runs}"),
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.set_text_color(0, 0, 0)

        if r.description:
            pdf.set_font("Helvetica", "I", 9)
            pdf.multi_cell(0, 5, _san(r.description, 500), new_x="LMARGIN", new_y="NEXT")

        self._field(pdf, f"Attack (injected at {r.injection_point}):", r.attack_payload, 1200)
        crit = "\n".join(f"- {c}" for c in r.criteria_descriptions)
        self._field(pdf, f"Success criteria ({r.combine_mode} must match):", crit, 800)

        ev = r.evidence_run
        if ev is not None:
            if ev.error:
                self._field(pdf, "Error:", ev.error, 800)
            elif ev.timed_out:
                self._field(pdf, "Result:", "No response within the timeout budget.", 200)
            else:
                label = ("Agent response (attack succeeded - evidence):"
                         if ev.attack_succeeded else "Agent response (representative):")
                self._field(pdf, label, ev.agent_response or "(empty response)", 1500)

        if r.verdict.value in ("FAIL", "FLAKY") and r.mitigations:
            self._field(pdf, "Recommended mitigations:",
                        "\n".join(f"- {m}" for m in r.mitigations), 800)
        pdf.ln(4)

    def _field(self, pdf: object, label: str, body: str, limit: int) -> None:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(110, 110, 110)
        pdf.multi_cell(0, 5, _san(label), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Courier", "", 8)
        pdf.multi_cell(0, 4, _san(body, limit), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)


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
  .tag { background:#1f6feb33; color:#79c0ff; padding:1px 6px; border-radius:999px; font-size:11px; }
  .desc { color:#c9d1d9; font-size:14px; margin:8px 0; }
  .block { margin:10px 0; }
  .lbl { color:var(--muted); font-size:12px; text-transform:uppercase;
         letter-spacing:.04em; margin-bottom:4px; }
  pre { white-space:pre-wrap; word-wrap:break-word; border-radius:8px; padding:10px 12px;
        font-size:12.5px; margin:0; max-height:320px; overflow:auto; }
  pre.payload { background:#2d2114; border:1px solid #5c3d1e; color:#ffd9a8; }
  pre.resp { background:#0d1b13; border:1px solid #1f4d2e; color:#aff5c8; }
  pre.err { background:#2d1418; border:1px solid #5c1e26; color:#ffb3b8; }
  ul.crit { margin:4px 0; padding-left:20px; font-size:13px; color:var(--muted); }
  ul.crit li.hit { color:#f85149; font-weight:600; }
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

  <h2>Scenarios &amp; findings</h2>
  {% for r in result.scenario_results %}
  <details {% if r.verdict.value in ["FAIL", "FLAKY"] %}open{% endif %}>
    <summary>
      {{ verdict_icon[r.verdict] }}
      <span class="{{ r.verdict.value }}">{{ r.verdict.value }}</span>
      &nbsp;{{ r.scenario_id }} — {{ r.scenario_name }}
    </summary>
    <div class="meta">{{ r.owasp_category }} {{ category_names[r.owasp_category] }}
      &middot; severity <strong>{{ r.severity }}</strong>
      {% if r.difficulty %}&middot; difficulty {{ r.difficulty }}{% endif %}
      &middot; attack succeeded {{ r.success_count }}/{{ r.num_runs }}
      &middot; {{ r.duration_ms }} ms
      {% if r.tags %}&middot; {% for t in r.tags %}<span class="tag">{{ t }}</span> {% endfor %}{% endif %}
    </div>

    {% if r.description %}<p class="desc">{{ r.description }}</p>{% endif %}

    <div class="block">
      <div class="lbl">Attack — injected at <code>{{ r.injection_point }}</code></div>
      <pre class="payload">{{ r.attack_payload }}</pre>
    </div>

    <div class="block">
      <div class="lbl">Success criteria ({{ r.combine_mode }} must match)</div>
      <ul class="crit">
        {% for c in r.criteria_descriptions %}
        <li{% if r.evidence_run and loop.index0 in r.evidence_run.matched_criteria %} class="hit"{% endif %}>
          {{ c }}{% if r.evidence_run and loop.index0 in r.evidence_run.matched_criteria %} ✓ matched{% endif %}
        </li>
        {% endfor %}
      </ul>
    </div>

    {% if r.evidence_run %}
    <div class="block">
      <div class="lbl">
        {% if r.evidence_run.error %}Error{% elif r.evidence_run.timed_out %}Timed out{%
        elif r.evidence_run.attack_succeeded %}Agent response (attack succeeded — evidence){%
        else %}Agent response (representative){% endif %}
      </div>
      {% if r.evidence_run.error %}<pre class="err">{{ r.evidence_run.error }}</pre>
      {% elif r.evidence_run.timed_out %}<pre class="err">No response within the timeout budget.</pre>
      {% else %}<pre class="resp">{{ r.evidence_run.agent_response or "(empty response)" }}</pre>{% endif %}
    </div>
    {% endif %}

    {% if r.verdict.value in ["FAIL", "FLAKY"] and r.mitigations %}
    <div class="mit">
      <strong>Recommended mitigations:</strong>
      <ul>{% for m in r.mitigations %}<li>{{ m }}</li>{% endfor %}</ul>
    </div>
    {% endif %}

    {% if r.references %}
    <div class="meta">References:
      {% for ref in r.references %}{% if ref.url.startswith("http://") or ref.url.startswith("https://") %}<a href="{{ ref.url }}" rel="noopener noreferrer">{{ ref.title or ref.url }}</a>{% else %}{{ ref.title or ref.url }}{% endif %}{% if not loop.last %} &middot; {% endif %}{% endfor %}
    </div>
    {% endif %}
  </details>
  {% endfor %}

  <p class="meta">Generated by aion-redteam. Fix findings with
    <a href="https://github.com/Cypharia/aion-guard" style="color:#58a6ff">aion-guard</a>.</p>
</div>
</body>
</html>
"""
