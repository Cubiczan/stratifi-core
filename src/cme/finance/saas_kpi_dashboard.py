"""SaaS KPI dashboard with CHP hardening and workbook export."""
from __future__ import annotations

import csv
import html
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from cme.chp.models import DecisionCase, Dossier, FoundationAttack, FoundationDisclosure


@dataclass
class DashboardMonth:
    month: str
    actuals: Dict[str, float]
    budget: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "month": self.month,
            "actuals": self.actuals,
            "budget": self.budget,
        }


@dataclass
class KPIValue:
    name: str
    actual: float
    budget: float
    variance: float
    variance_pct: float | None
    favorable: bool
    sparkline: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VarianceRow:
    metric: str
    actual: float
    budget: float
    variance: float
    variance_pct: float | None
    favorable: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SaaSKPIDashboardResult:
    months: List[DashboardMonth]
    kpis: List[KPIValue]
    variance_rows: List[VarianceRow]
    key_findings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "months": [row.to_dict() for row in self.months],
            "kpis": [item.to_dict() for item in self.kpis],
            "variance_rows": [row.to_dict() for row in self.variance_rows],
            "key_findings": self.key_findings,
        }


def load_saas_dashboard_csv(path: str | Path) -> Dict[str, Dict[str, float]]:
    dataset: Dict[str, Dict[str, float]] = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            month = (raw.get("Month") or raw.get("month") or "").strip()
            if not month:
                continue
            values = {
                key.strip(): _to_float(value)
                for key, value in raw.items()
                if key and key.strip() != "Month"
            }
            dataset[month] = _derive_metrics(values)
    return dataset


def build_saas_kpi_dashboard(
    actuals: Dict[str, Dict[str, float]],
    budget: Dict[str, Dict[str, float]],
) -> SaaSKPIDashboardResult:
    month_labels = sorted(set(actuals) | set(budget))
    months = [
        DashboardMonth(
            month=label,
            actuals=_derive_metrics(actuals.get(label, {})),
            budget=_derive_metrics(budget.get(label, {})),
        )
        for label in month_labels
    ]

    latest = months[-1]
    kpi_names = [
        "MRR",
        "ARR",
        "Revenue",
        "Gross Margin %",
        "EBITDA",
        "EBITDA Margin",
        "Rule of 40",
        "CAC",
        "LTV",
    ]
    kpis = [_build_kpi(name, months, latest) for name in kpi_names]

    variance_metric_names = [
        "MRR",
        "Revenue",
        "Gross Margin %",
        "CAC",
        "LTV",
        "EBITDA",
        "EBITDA Margin",
        "Rule of 40",
    ]
    variance_rows = [
        _variance_row(name, latest.actuals.get(name, 0.0), latest.budget.get(name, 0.0))
        for name in variance_metric_names
    ]
    variance_rows.sort(key=lambda row: abs(row.variance), reverse=True)

    return SaaSKPIDashboardResult(
        months=months,
        kpis=kpis,
        variance_rows=variance_rows,
        key_findings=_build_key_findings(months, kpis, variance_rows),
    )


def build_saas_kpi_dashboard_case(
    result: SaaSKPIDashboardResult,
    *,
    owner: str = "cfo",
    origin_system: str = "Claude",
    origin_model: str = "GPT-5.4",
    partner_system: str = "Partner",
    partner_model: str = "GPT-5-equivalent",
) -> tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    latest = result.months[-1]
    negative_kpis = [
        row.metric
        for row in result.variance_rows
        if not row.favorable and abs(row.variance_pct or 0.0) >= 0.05
    ]
    dossier = Dossier(
        core_problem="Pressure-test the SaaS KPI dashboard before it is used for operating review, investor reporting, or board discussion.",
        goal_state=[
            "Actual versus budget movement is visible at the KPI level",
            "Derived metrics are internally consistent and auditable",
            "Management can see where growth quality or profitability is slipping",
        ],
        current_state=[
            f"Latest month is {latest.month}",
            f"MRR actual is {_fmt(latest.actuals.get('MRR', 0.0), 'MRR')}",
            f"Revenue actual is {_fmt(latest.actuals.get('Revenue', 0.0), 'Revenue')}",
            f"Rule of 40 actual is {_fmt(latest.actuals.get('Rule of 40', 0.0), 'Rule of 40')}",
        ],
        prior_decisions=[],
        constraints=[
            "Dashboard consumes replaceable actuals and budget files",
            "Derived KPIs are calculated from a compact driver set",
            "Views are designed for operator and board readability",
        ],
        unknowns=[
            "Source files may mix accounting and operating definitions across months",
            "Some KPIs can appear favorable for the wrong reason if data hygiene slips",
        ],
        scope=[
            "KPI cards",
            "Budget variance",
            "Trend views",
            "Finance operating narrative",
        ],
        origin_direction=[
            "Prefer auditable metric derivation over cosmetic dashboard complexity",
            "Treat budget variance as a diagnostic surface, not just a visual summary",
        ],
        structural_vulnerabilities=[
            "Derived metrics can look precise even when base source definitions are inconsistent",
            "Budget comparisons can produce false comfort if the budget baseline itself is weak",
        ],
    )
    case = DecisionCase(
        decision_id=f"saas-kpi-dashboard-{latest.month.lower().replace(' ', '-')}",
        title="SaaS KPI dashboard",
        domain="saas_kpi_dashboard",
        created_at=datetime.now(timezone.utc).isoformat(),
        owner=owner,
        high_stakes=True,
        origin_system=origin_system,
        origin_model=origin_model,
        partner_system=partner_system,
        partner_model=partner_model,
        dossier=dossier,
    )
    disclosure = FoundationDisclosure(
        weakest_assumptions=[
            "The actuals and budget files share the same KPI definitions by month",
            "Derived metrics like EBITDA Margin and Rule of 40 are directionally sufficient for review use",
            "A lightweight dashboard surface can preserve enough context for executive decisions",
        ],
        invalidation_conditions=[
            "Source files use inconsistent definitions or omit a required base metric",
            "Budget baselines are stale enough to distort the variance narrative",
        ],
        key_vulnerability="The dashboard is most exposed where clean visuals hide messy source definitions.",
    )
    score = 86
    score -= min(12, len(negative_kpis) * 2)
    if latest.actuals.get("Rule of 40", 0.0) < 0.20:
        score -= 6
    attack = FoundationAttack(
        assumption_attacks=[
            "A unified dashboard can overstate comparability when source definitions change over time.",
            "Derived KPIs may create confidence without proving source hygiene month by month.",
            "Management can anchor on card-level variance instead of the operational drivers underneath it.",
        ],
        invalidation_exploitation=[
            "One mislabeled base metric can ripple into EBITDA Margin and Rule of 40 without being obvious at first glance.",
            "A weak budget baseline can make actuals look better or worse than the real operating trend.",
        ],
        vulnerability_strike="The dashboard succeeds only if users trust the metric spine more than the visual polish.",
        foundation_score=max(60, min(92, score)),
        attack_summary="The dashboard is useful for rapid review, but only if the KPI definitions and budget baselines are challenged before the charts are trusted.",
    )
    dossier.foundation_score = attack.foundation_score
    dossier.prior_round_summary = [f"Latest unfavorable KPIs: {', '.join(negative_kpis[:4]) or 'NONE'}"]
    return case, disclosure, attack


def render_saas_kpi_dashboard_markdown(result: SaaSKPIDashboardResult) -> str:
    latest = result.months[-1]
    lines = [
        "# SaaS KPI Dashboard",
        f"**Latest Month:** {latest.month}",
        "",
        "## Key Findings",
    ]
    for finding in result.key_findings:
        lines.append(f"- {finding}")
    lines.extend(["", "## KPI Snapshot"])
    for item in result.kpis:
        variance = _fmt(item.variance, item.name)
        pct = f" ({item.variance_pct * 100:+.1f}%)" if item.variance_pct is not None else ""
        lines.append(
            f"- {item.name}: actual={_fmt(item.actual, item.name)} | "
            f"budget={_fmt(item.budget, item.name)} | variance={variance}{pct}"
        )
    return "\n".join(lines)


def render_saas_kpi_dashboard_html(
    result: SaaSKPIDashboardResult,
    *,
    session_summary: str | None = None,
) -> str:
    latest = result.months[-1]
    kpi_cards = "".join(_kpi_card(item) for item in result.kpis)
    variance_rows = "".join(
        (
            f"<tr><td>{html.escape(row.metric)}</td>"
            f"<td>{html.escape(_fmt(row.actual, row.metric))}</td>"
            f"<td>{html.escape(_fmt(row.budget, row.metric))}</td>"
            f"<td class=\"{'good' if row.favorable else 'bad'}\">{html.escape(_fmt(row.variance, row.metric))}</td>"
            f"<td>{html.escape('n/a' if row.variance_pct is None else f'{row.variance_pct * 100:+.1f}%')}</td></tr>"
        )
        for row in result.variance_rows
    )
    findings = "".join(f"<li>{html.escape(item)}</li>" for item in result.key_findings)
    chart_blocks = "".join(
        [
            _chart_block("MRR vs Budget", result.months, "MRR"),
            _chart_block("Revenue vs OpEx", result.months, "Revenue", "OpEx"),
            _chart_block("Gross Margin %", result.months, "Gross Margin %"),
            _chart_block("CAC vs LTV", result.months, "CAC", "LTV"),
            _chart_block("EBITDA", result.months, "EBITDA"),
            _chart_block("EBITDA Margin", result.months, "EBITDA Margin"),
        ]
    )
    session = (
        f"<section class=\"panel\"><h2>CHP Session Summary</h2><pre>{html.escape(session_summary)}</pre></section>"
        if session_summary
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SaaS KPI Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      --bg: #0d1320;
      --panel: #111a2c;
      --panel-alt: #172338;
      --line: #2b3c58;
      --text: #e6edf8;
      --muted: #9cb0ce;
      --good: #4ed9a5;
      --bad: #ff8b8b;
      --accent: #7cc4ff;
      --accent-2: #ffce73;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(124,196,255,0.14), transparent 26%),
        radial-gradient(circle at bottom right, rgba(255,206,115,0.12), transparent 22%),
        var(--bg);
      color: var(--text);
    }}
    .shell {{ max-width: 1360px; margin: 0 auto; padding: 28px; }}
    .hero {{
      background: linear-gradient(135deg, rgba(124,196,255,0.17), rgba(255,206,115,0.08));
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 28px;
      display: grid;
      gap: 12px;
      margin-bottom: 24px;
    }}
    .eyebrow {{ color: var(--muted); text-transform: uppercase; letter-spacing: 0.12em; font-size: 12px; }}
    h1, h2, h3 {{ margin: 0; }}
    .grid {{ display: grid; gap: 16px; }}
    .kpis {{ grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-bottom: 24px; }}
    .two {{ grid-template-columns: 2fr 1fr; align-items: start; margin-bottom: 24px; }}
    .charts {{ grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }}
    .panel {{
      background: rgba(17, 26, 44, 0.92);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 18px;
      box-shadow: 0 18px 48px rgba(0, 0, 0, 0.24);
    }}
    .card-value {{ font-size: 28px; font-weight: 700; margin-top: 8px; }}
    .subtle {{ color: var(--muted); font-size: 13px; }}
    .good {{ color: var(--good); }}
    .bad {{ color: var(--bad); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; }}
    th {{ color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }}
    ul {{ margin: 12px 0 0; padding-left: 18px; }}
    pre {{ white-space: pre-wrap; color: var(--muted); font-size: 12px; }}
    .legend {{ display: flex; gap: 12px; font-size: 12px; color: var(--muted); margin-top: 8px; }}
    .swatch {{ display: inline-block; width: 10px; height: 10px; border-radius: 99px; margin-right: 6px; }}
    @media (max-width: 960px) {{
      .two {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="eyebrow">Consensus Hardening Protocol | SaaS KPI Dashboard</div>
      <h1>Operating Snapshot for {html.escape(latest.month)}</h1>
      <div class="subtle">Budget-aware KPI surface for revenue quality, efficiency, and profitability.</div>
    </section>
    <section class="grid kpis">{kpi_cards}</section>
    <section class="grid two">
      <div class="panel">
        <h2>Variance Table</h2>
        <table>
          <thead><tr><th>Metric</th><th>Actual</th><th>Budget</th><th>Variance</th><th>Variance %</th></tr></thead>
          <tbody>{variance_rows}</tbody>
        </table>
      </div>
      <div class="panel">
        <h2>Key Findings</h2>
        <ul>{findings}</ul>
      </div>
    </section>
    <section class="grid charts">{chart_blocks}</section>
    {session}
  </div>
</body>
</html>
"""


def export_saas_kpi_dashboard_workbook(
    result: SaaSKPIDashboardResult,
    *,
    session_summary: str,
    output_path: str | Path,
) -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    builder_path = repo_root / "tools" / "build_saas_kpi_dashboard_workbook.mjs"
    node_path = _resolve_node_path()
    _ensure_node_modules_link(repo_root)
    payload = {"dashboard": result.to_dict(), "session_summary": session_summary}
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        temp_json = Path(handle.name)

    try:
        subprocess.run(
            [node_path, str(builder_path), str(temp_json), str(output_file)],
            check=True,
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr or exc.stdout or "Workbook export failed.") from exc
    finally:
        temp_json.unlink(missing_ok=True)

    return output_file


def _build_kpi(name: str, months: Iterable[DashboardMonth], latest: DashboardMonth) -> KPIValue:
    actual = latest.actuals.get(name, 0.0)
    budget = latest.budget.get(name, 0.0)
    variance = actual - budget
    variance_pct = _variance_pct(actual, budget)
    sparkline = [month.actuals.get(name, 0.0) for month in months][-12:]
    return KPIValue(
        name=name,
        actual=actual,
        budget=budget,
        variance=variance,
        variance_pct=variance_pct,
        favorable=_is_favorable(name, variance),
        sparkline=sparkline,
    )


def _variance_row(metric: str, actual: float, budget: float) -> VarianceRow:
    variance = actual - budget
    return VarianceRow(
        metric=metric,
        actual=actual,
        budget=budget,
        variance=variance,
        variance_pct=_variance_pct(actual, budget),
        favorable=_is_favorable(metric, variance),
    )


def _build_key_findings(
    months: List[DashboardMonth],
    kpis: List[KPIValue],
    variance_rows: List[VarianceRow],
) -> List[str]:
    latest = months[-1]
    findings: List[str] = []
    mrr = latest.actuals.get("MRR", 0.0)
    revenue = latest.actuals.get("Revenue", 0.0)
    rule_40 = latest.actuals.get("Rule of 40", 0.0)
    ebitda_margin = latest.actuals.get("EBITDA Margin", 0.0)
    if rule_40 >= 0.40:
        findings.append(f"Rule of 40 is at {_fmt(rule_40, 'Rule of 40')}, indicating balanced growth and profitability.")
    else:
        findings.append(f"Rule of 40 is only {_fmt(rule_40, 'Rule of 40')}, so growth quality needs attention before the next board cycle.")
    findings.append(f"Latest MRR is {_fmt(mrr, 'MRR')} on revenue of {_fmt(revenue, 'Revenue')}.")
    top_variance = variance_rows[0]
    direction = "ahead of" if top_variance.favorable else "behind"
    findings.append(
        f"The biggest KPI gap is {top_variance.metric}, running {direction} budget by {_fmt(top_variance.variance, top_variance.metric)}."
    )
    if ebitda_margin < 0:
        findings.append("EBITDA margin is negative, so topline progress is not yet translating into operating leverage.")
    cac = next((item for item in kpis if item.name == "CAC"), None)
    ltv = next((item for item in kpis if item.name == "LTV"), None)
    if cac and ltv and cac.actual > 0:
        findings.append(f"LTV/CAC is {ltv.actual / cac.actual:.1f}x, which frames how efficiently the growth engine is converting spend.")
    return findings


def _derive_metrics(values: Dict[str, float]) -> Dict[str, float]:
    derived = dict(values)
    revenue = derived.get("Revenue", 0.0)
    cogs = derived.get("COGS", 0.0)
    sales_marketing = derived.get("Sales & Marketing", 0.0)
    rnd = derived.get("R&D", 0.0)
    gna = derived.get("G&A", 0.0)
    opex = derived.get("OpEx", sales_marketing + rnd + gna)
    derived["OpEx"] = opex
    derived.setdefault("ARR", derived.get("MRR", 0.0) * 12)
    if revenue:
        derived.setdefault("Gross Margin %", (revenue - cogs) / revenue)
    else:
        derived.setdefault("Gross Margin %", 0.0)
    ebitda = derived.get("EBITDA", revenue - cogs - opex)
    derived["EBITDA"] = ebitda
    derived["EBITDA Margin"] = ebitda / revenue if revenue else 0.0
    yoy_growth = derived.get("YoY Growth", 0.0)
    derived["Rule of 40"] = yoy_growth + derived["EBITDA Margin"]
    return derived


def _metric_format(metric: str) -> str:
    return "pct" if metric in {"Gross Margin %", "EBITDA Margin", "Rule of 40", "NRR %", "GRR %", "YoY Growth", "Churn Rate"} else "money"


def _fmt(value: float, metric: str) -> str:
    if _metric_format(metric) == "pct":
        return f"{value * 100:.1f}%"
    return f"${value:,.0f}"


def _variance_pct(actual: float, budget: float) -> float | None:
    if abs(budget) < 1e-9:
        return None
    return (actual - budget) / budget


def _is_favorable(metric: str, variance: float) -> bool:
    lower_is_better = {"CAC", "COGS", "OpEx"}
    return variance <= 0 if metric in lower_is_better else variance >= 0


def _kpi_card(item: KPIValue) -> str:
    delta_text = "n/a" if item.variance_pct is None else f"{item.variance_pct * 100:+.1f}%"
    return (
        f"<article class=\"panel\">"
        f"<div class=\"subtle\">{html.escape(item.name)}</div>"
        f"<div class=\"card-value\">{html.escape(_fmt(item.actual, item.name))}</div>"
        f"<div class=\"{'good' if item.favorable else 'bad'}\">vs budget {html.escape(_fmt(item.variance, item.name))} | {html.escape(delta_text)}</div>"
        f"{_spark_svg(item.sparkline, '#7cc4ff')}"
        f"</article>"
    )


def _chart_block(title: str, months: List[DashboardMonth], primary: str, secondary: str | None = None) -> str:
    actual_points = [month.actuals.get(primary, 0.0) for month in months][-12:]
    budget_points = [month.budget.get(primary, 0.0) for month in months][-12:]
    if secondary:
        actual_secondary = [month.actuals.get(secondary, 0.0) for month in months][-12:]
        lines = _multi_line_svg(
            [
                (actual_points, "#7cc4ff"),
                (actual_secondary, "#ffce73"),
            ]
        )
        legend = (
            f"<div class=\"legend\"><span><span class=\"swatch\" style=\"background:#7cc4ff\"></span>{html.escape(primary)}</span>"
            f"<span><span class=\"swatch\" style=\"background:#ffce73\"></span>{html.escape(secondary)}</span></div>"
        )
    else:
        lines = _multi_line_svg(
            [
                (actual_points, "#7cc4ff"),
                (budget_points, "#ffce73"),
            ]
        )
        legend = (
            f"<div class=\"legend\"><span><span class=\"swatch\" style=\"background:#7cc4ff\"></span>Actual</span>"
            f"<span><span class=\"swatch\" style=\"background:#ffce73\"></span>Budget</span></div>"
        )
    return f"<article class=\"panel\"><h3>{html.escape(title)}</h3>{lines}{legend}</article>"


def _spark_svg(points: List[float], color: str) -> str:
    return _multi_line_svg([(points, color)], width=190, height=56)


def _multi_line_svg(series: List[tuple[List[float], str]], width: int = 320, height: int = 140) -> str:
    all_points = [value for points, _ in series for value in points]
    if not all_points:
        return f"<svg viewBox='0 0 {width} {height}' width='{width}' height='{height}'></svg>"
    lo = min(all_points)
    hi = max(all_points)
    spread = hi - lo or 1.0
    step = width / max(1, max(len(points) for points, _ in series) - 1)
    paths = []
    for points, color in series:
        coords = [
            (idx * step, height - ((value - lo) / spread) * (height - 18) - 9)
            for idx, value in enumerate(points)
        ]
        path = " ".join(
            [f"M {coords[0][0]:.1f} {coords[0][1]:.1f}"] +
            [f"L {x:.1f} {y:.1f}" for x, y in coords[1:]]
        )
        paths.append(f"<path d='{path}' fill='none' stroke='{color}' stroke-width='3' stroke-linecap='round' />")
    return f"<svg viewBox='0 0 {width} {height}' width='100%' height='{height}'>{''.join(paths)}</svg>"


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text:
        return 0.0
    if text.endswith("%"):
        return float(text[:-1]) / 100.0
    return float(text)


def _ensure_node_modules_link(repo_root: Path) -> None:
    target = repo_root / "node_modules"
    if target.exists():
        return
    source = repo_root.parent / "node_modules"
    if source.exists():
        os.symlink(source, target, target_is_directory=True)


def _resolve_node_path() -> str:
    configured = os.environ.get("NODE_BINARY")
    if configured:
        return configured
    node = shutil.which("node")
    if node:
        return node
    raise RuntimeError("Node.js executable not found. Set NODE_BINARY or install node.")
