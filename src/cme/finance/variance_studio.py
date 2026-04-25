"""Monthly CFO Variance Studio domain logic."""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from cme.chp.models import DecisionCase, Dossier, FoundationAttack, FoundationDisclosure


REQUIRED_COLUMNS = {
    "period",
    "entity",
    "department",
    "account",
    "category",
    "actual",
    "budget",
}


@dataclass
class VarianceRow:
    period: str
    entity: str
    department: str
    account: str
    category: str
    actual: float
    budget: float


@dataclass
class VarianceDriver:
    driver_name: str
    actual: float
    budget: float
    variance: float
    variance_pct: float
    category: str
    insight: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VarianceBucket:
    label: str
    actual: float
    budget: float
    variance: float
    variance_pct: float
    count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VarianceKPI:
    label: str
    actual: float
    budget: float
    variance: float
    variance_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NarrativeItem:
    text: str
    severity: Optional[str] = None
    size_hint: Optional[str] = None
    owner_hint: Optional[str] = None
    expected_impact_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditTrailItem:
    statement: str
    linked_numbers: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VarianceStudioResult:
    period: str
    entity: str
    group_by: str
    materiality_mode: str = "auto"
    data_quality_warnings: List[str] = field(default_factory=list)
    materiality_threshold_abs: float = 0.0
    materiality_threshold_pct: float = 0.0
    shown_driver_count: int = 0
    kpis: List[VarianceKPI] = field(default_factory=list)
    drivers: List[VarianceDriver] = field(default_factory=list)
    visible_drivers: List[VarianceDriver] = field(default_factory=list)
    other_bucket: Optional[VarianceBucket] = None
    spotlight_driver: Optional[VarianceDriver] = None
    exec_summary_bullets: List[str] = field(default_factory=list)
    risks: List[NarrativeItem] = field(default_factory=list)
    opportunities: List[NarrativeItem] = field(default_factory=list)
    suggested_actions: List[NarrativeItem] = field(default_factory=list)
    audit_trail: List[AuditTrailItem] = field(default_factory=list)
    ceo_narrative: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "entity": self.entity,
            "group_by": self.group_by,
            "data_quality_warnings": self.data_quality_warnings,
            "materiality_threshold_abs": self.materiality_threshold_abs,
            "materiality_threshold_pct": self.materiality_threshold_pct,
            "shown_driver_count": self.shown_driver_count,
            "kpis": [item.to_dict() for item in self.kpis],
            "drivers": [item.to_dict() for item in self.drivers],
            "visible_drivers": [item.to_dict() for item in self.visible_drivers],
            "other_bucket": self.other_bucket.to_dict() if self.other_bucket else None,
            "spotlight_driver": self.spotlight_driver.to_dict() if self.spotlight_driver else None,
            "exec_summary_bullets": self.exec_summary_bullets,
            "risks": [item.to_dict() for item in self.risks],
            "opportunities": [item.to_dict() for item in self.opportunities],
            "suggested_actions": [item.to_dict() for item in self.suggested_actions],
            "audit_trail": [item.to_dict() for item in self.audit_trail],
            "ceo_narrative": self.ceo_narrative,
        }


def load_variance_csv(path: str | Path) -> tuple[List[VarianceRow], List[str]]:
    rows: List[VarianceRow] = []
    warnings: List[str] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - {name.strip().lower() for name in (reader.fieldnames or [])}
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
        for idx, raw in enumerate(reader, start=2):
            try:
                actual = _to_float(raw["actual"])
                budget = _to_float(raw["budget"])
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"row {idx}: invalid numeric values ({exc})")
                continue
            category = raw["category"].strip()
            if category not in {"Revenue", "COGS", "OPEX"}:
                warnings.append(f"row {idx}: unexpected category '{category}'")
            if budget == 0:
                warnings.append(f"row {idx}: zero budget for {raw['account']}")
            rows.append(
                VarianceRow(
                    period=raw["period"].strip(),
                    entity=raw["entity"].strip(),
                    department=raw["department"].strip(),
                    account=raw["account"].strip(),
                    category=category,
                    actual=actual,
                    budget=budget,
                )
            )
    return rows, _dedupe_preserve_order(warnings)


def analyze_variance(
    rows: Iterable[VarianceRow],
    *,
    period: str | None = None,
    entity: str | None = None,
    group_by: str = "account",
    materiality_mode: str = "auto",
    abs_threshold: float | None = None,
    pct_threshold: float | None = None,
) -> VarianceStudioResult:
    rows = list(rows)
    if not rows:
        raise ValueError("no rows available for analysis")
    period = period or max(row.period for row in rows)
    entity = entity or rows[0].entity
    filtered = [row for row in rows if row.period == period and row.entity == entity]
    if not filtered:
        raise ValueError(f"no rows found for period={period} entity={entity}")

    warnings = _data_quality_checks(filtered)
    metrics = _build_kpis(filtered)
    drivers = _aggregate_drivers(filtered, group_by=group_by)
    if materiality_mode == "auto":
        abs_threshold, pct_threshold, shown_count = _auto_materiality(drivers)
    elif materiality_mode == "manual":
        abs_threshold = max(abs_threshold or 0.0, 0.0)
        pct_threshold = max(pct_threshold or 0.0, 0.0)
        shown_count = 0
    else:
        raise ValueError("materiality_mode must be 'auto' or 'manual'")
    visible_drivers, other_bucket = _apply_materiality(
        drivers,
        abs_threshold=abs_threshold,
        pct_threshold=pct_threshold,
    )
    shown_count = len(visible_drivers)
    top3 = sorted(drivers, key=lambda item: abs(item.variance), reverse=True)[:3]
    spotlight = top3[0] if top3 else None
    narrative = _build_ceo_narrative(top3, metrics)
    exec_summary_bullets = _build_exec_summary_bullets(top3, metrics)
    risks = _build_risks(top3, warnings)
    opportunities = _build_opportunities(top3)
    suggested_actions = _build_suggested_actions(top3)
    audit_trail = _build_audit_trail(top3, metrics, other_bucket)
    return VarianceStudioResult(
        period=period,
        entity=entity,
        group_by=group_by,
        materiality_mode=materiality_mode,
        data_quality_warnings=warnings,
        materiality_threshold_abs=abs_threshold,
        materiality_threshold_pct=pct_threshold,
        shown_driver_count=shown_count,
        kpis=metrics,
        drivers=top3,
        visible_drivers=visible_drivers,
        other_bucket=other_bucket,
        spotlight_driver=spotlight,
        exec_summary_bullets=exec_summary_bullets,
        risks=risks,
        opportunities=opportunities,
        suggested_actions=suggested_actions,
        audit_trail=audit_trail,
        ceo_narrative=narrative,
    )


def build_variance_case(
    result: VarianceStudioResult,
    *,
    owner: str = "cfo",
    origin_system: str = "Claude",
    origin_model: str = "GPT-5.4",
    partner_system: str = "Partner",
    partner_model: str = "GPT-5-equivalent",
) -> tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    decision_id = _slugify(f"variance-{result.entity}-{result.period}")[:40]
    top_driver_names = [driver.driver_name for driver in result.drivers[:3]]
    warning_count = len(result.data_quality_warnings)
    dossier = Dossier(
        core_problem=f"Identify and harden the top monthly performance drivers for {result.entity} in {result.period}.",
        goal_state=[
            "Top 3 drivers are ranked by absolute budget variance",
            "Narrative is grounded in KPI and driver values",
            "Board-ready commentary is defensible before lock",
        ],
        current_state=[
            f"Analysis grouped by {result.group_by}",
            f"{len(result.drivers)} candidate drivers identified for top-driver review",
            f"{warning_count} data quality warning(s) detected",
        ],
        constraints=[
            "Do not invent unsupported causal explanations",
            "Top 3 selections must match absolute variance ranking",
        ],
        unknowns=[
            "Root cause detail outside the uploaded finance file",
            "Cross-functional context not yet provided by operators",
        ],
        scope=[
            "Driver ranking",
            "Narrative hardening",
            "Action recommendation lock",
        ],
        origin_direction=[
            "Prefer grounded narrative over polished but unsupported explanation",
            "Escalate assumptions when data quality is weak",
        ],
        structural_vulnerabilities=[
            "Variance narrative can overstate causality if operational context is missing",
            "Weak file quality can distort rank ordering",
        ],
    )
    case = DecisionCase(
        decision_id=decision_id,
        title=f"Monthly variance review for {result.entity} {result.period}",
        domain="variance_copilot",
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
            "The uploaded file has enough granularity to explain the top three drivers",
            "Budget is the correct comparison baseline for all included accounts",
            "Account-level aggregation is the right grain for the current narrative",
        ],
        invalidation_conditions=[
            "Material file quality issues change the driver ranking",
            "Management context contradicts the initial numeric explanation",
        ],
        key_vulnerability="The story can sound stronger than the evidence if the numeric ranking is correct but the cause is not yet validated.",
    )
    score = max(60, 84 - warning_count * 5)
    attack = FoundationAttack(
        assumption_attacks=[
            "The file may be sufficient for ranking but insufficient for causal explanation.",
            "Budget comparisons may hide reclasses, phasing shifts, or one-offs.",
            "Grouping by account may miss the real management story if the issue is departmental.",
        ],
        invalidation_exploitation=[
            "A small file defect can change the top-three selection if driver magnitudes are close.",
            "Management commentary may reverse the initial interpretation even when the math is right.",
        ],
        vulnerability_strike="The highest risk is false narrative confidence, not arithmetic failure.",
        foundation_score=score,
        attack_summary="The variance logic is useful, but the narrative must remain disciplined. Rank can be trusted faster than explanation unless supporting context is added.",
    )
    dossier.foundation_score = score
    dossier.prior_round_summary = [f"Initial top drivers: {', '.join(top_driver_names)}"] if top_driver_names else []
    return case, disclosure, attack


def render_variance_markdown(result: VarianceStudioResult, *, include_checklist: bool = True) -> str:
    lines: List[str] = [f"# Monthly CFO Variance Studio", f"**Period:** {result.period}", f"**Entity:** {result.entity}", ""]
    if include_checklist:
        lines.extend(
            [
                "## Checklist",
                "- Validate source rows and required columns",
                "- Rank drivers by absolute budget variance",
                "- Cross-check KPI movement against driver list",
                "- Keep unsupported claims out of the narrative",
                "",
            ]
        )
    lines.append("## KPI Summary")
    for kpi in result.kpis:
        lines.append(
            f"- {kpi.label}: actual={kpi.actual:,.2f} budget={kpi.budget:,.2f} "
            f"var={kpi.variance:,.2f} ({kpi.variance_pct:.1%})"
        )
    lines.append("")
    lines.append("## Materiality")
    lines.append(f"- mode={result.materiality_mode}")
    lines.append(f"- abs_threshold={result.materiality_threshold_abs:,.2f}")
    lines.append(f"- pct_threshold={result.materiality_threshold_pct:.1%}")
    lines.append(f"- shown_drivers={result.shown_driver_count}")
    lines.append("")
    lines.append("## Visible Drivers")
    for driver in result.visible_drivers:
        lines.append(
            f"- {driver.driver_name}: actual={driver.actual:,.2f} budget={driver.budget:,.2f} "
            f"var={driver.variance:,.2f} ({driver.variance_pct:.1%})"
        )
    if result.other_bucket:
        lines.append(
            f"- {result.other_bucket.label}: actual={result.other_bucket.actual:,.2f} "
            f"budget={result.other_bucket.budget:,.2f} var={result.other_bucket.variance:,.2f} "
            f"({result.other_bucket.variance_pct:.1%}) across {result.other_bucket.count} items"
        )
    lines.append("")
    lines.append("## Top Drivers")
    for idx, driver in enumerate(result.drivers, start=1):
        lines.append(
            f"{idx}. {driver.driver_name} | actual={driver.actual:,.2f} | "
            f"budget={driver.budget:,.2f} | var={driver.variance:,.2f} ({driver.variance_pct:.1%})"
        )
        lines.append(f"   Insight: {driver.insight}")
        lines.append(f"   Recommendation: {driver.recommendation}")
    if result.data_quality_warnings:
        lines.append("")
        lines.append("## Data Quality Warnings")
        for warning in result.data_quality_warnings:
            lines.append(f"- {warning}")
    if result.exec_summary_bullets:
        lines.append("")
        lines.append("## Executive Summary")
        for item in result.exec_summary_bullets:
            lines.append(f"- {item}")
    if result.spotlight_driver:
        lines.append("")
        lines.append("## Spotlight Driver")
        lines.append(
            f"- {result.spotlight_driver.driver_name}: variance={result.spotlight_driver.variance:,.2f} "
            f"({result.spotlight_driver.variance_pct:.1%})"
        )
        lines.append(f"- Explanation: {result.spotlight_driver.insight}")
    if result.risks:
        lines.append("")
        lines.append("## Risks")
        for risk in result.risks:
            suffix = f" [{risk.severity}]" if risk.severity else ""
            lines.append(f"- {risk.text}{suffix}")
    if result.opportunities:
        lines.append("")
        lines.append("## Opportunities")
        for item in result.opportunities:
            suffix = f" [{item.size_hint}]" if item.size_hint else ""
            lines.append(f"- {item.text}{suffix}")
    if result.suggested_actions:
        lines.append("")
        lines.append("## Suggested Actions")
        for item in result.suggested_actions:
            owner = f" | owner={item.owner_hint}" if item.owner_hint else ""
            impact = f" | impact={item.expected_impact_hint}" if item.expected_impact_hint else ""
            lines.append(f"- {item.text}{owner}{impact}")
    if result.audit_trail:
        lines.append("")
        lines.append("## Audit Trail")
        for item in result.audit_trail:
            numbers = ", ".join(f"{n['label']}={n['value']}" for n in item.linked_numbers)
            lines.append(f"- {item.statement} :: {numbers}")
    lines.append("")
    lines.append("## CEO Narrative")
    lines.append(result.ceo_narrative)
    return "\n".join(lines)


def render_variance_html(result: VarianceStudioResult, *, session_summary: str = "") -> str:
    kpi_cards = "\n".join(
        f"""
        <div class="card kpi">
          <div class="label">{_escape_html(kpi.label)}</div>
          <div class="value">{_fmt_currency(kpi.actual)}</div>
          <div class="sub">Budget {_fmt_currency(kpi.budget)}</div>
          <div class="variance {'neg' if kpi.variance < 0 else 'pos'}">
            Var {_fmt_currency(kpi.variance)} ({kpi.variance_pct:.1%})
          </div>
        </div>
        """
        for kpi in result.kpis
    )

    visible_rows = "\n".join(
        f"""
        <tr>
          <td>{_escape_html(driver.driver_name)}</td>
          <td>{_escape_html(driver.category)}</td>
          <td>{_fmt_currency(driver.actual)}</td>
          <td>{_fmt_currency(driver.budget)}</td>
          <td class="{'neg' if driver.variance < 0 else 'pos'}">{_fmt_currency(driver.variance)}</td>
          <td>{driver.variance_pct:.1%}</td>
        </tr>
        """
        for driver in result.visible_drivers
    )

    top_driver_blocks = "\n".join(
        f"""
        <div class="card driver">
          <h3>{_escape_html(driver.driver_name)}</h3>
          <p class="metric {'neg' if driver.variance < 0 else 'pos'}">{_fmt_currency(driver.variance)} ({driver.variance_pct:.1%})</p>
          <p>{_escape_html(driver.insight)}</p>
          <p><strong>Recommendation:</strong> {_escape_html(driver.recommendation)}</p>
        </div>
        """
        for driver in result.drivers
    )

    exec_bullets = "".join(f"<li>{_escape_html(item)}</li>" for item in result.exec_summary_bullets)
    risks = "".join(
        f"<li><strong>{_escape_html(item.severity or 'info')}:</strong> {_escape_html(item.text)}</li>"
        for item in result.risks
    )
    opportunities = "".join(
        f"<li>{_escape_html(item.text)}"
        f"{f' <span class=\"pill\">{_escape_html(item.size_hint)}</span>' if item.size_hint else ''}</li>"
        for item in result.opportunities
    )
    actions = "".join(
        f"<li>{_escape_html(item.text)}"
        f"{f' <span class=\"meta\">owner={_escape_html(item.owner_hint)}</span>' if item.owner_hint else ''}"
        f"{f' <span class=\"meta\">impact={_escape_html(item.expected_impact_hint)}</span>' if item.expected_impact_hint else ''}"
        f"</li>"
        for item in result.suggested_actions
    )
    audit_items = "".join(
        f"<li>{_escape_html(item.statement)} :: "
        + ", ".join(
            f"{_escape_html(str(number['label']))}={_escape_html(str(number['value']))}"
            for number in item.linked_numbers
        )
        + "</li>"
        for item in result.audit_trail
    )

    other_bucket = ""
    if result.other_bucket:
        other_bucket = (
            f"<div class='card'><h3>Other Bucket</h3>"
            f"<p>{_fmt_currency(result.other_bucket.variance)} ({result.other_bucket.variance_pct:.1%}) across "
            f"{result.other_bucket.count} hidden items</p></div>"
        )

    session_block = (
        f"<section class='section'><h2>CHP Session</h2><pre>{_escape_html(session_summary)}</pre></section>"
        if session_summary
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Monthly CFO Variance Studio</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --panel: #fffdf8;
      --ink: #1f2520;
      --muted: #657166;
      --line: #d8cfbf;
      --accent: #134e4a;
      --warn: #b45309;
      --good: #166534;
      --bad: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #f1eadb 0%, #f7f4ed 100%);
      color: var(--ink);
    }}
    .wrap {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 24px 56px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 20px;
      align-items: start;
      margin-bottom: 24px;
    }}
    .hero-card, .card, .section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 12px 32px rgba(31, 37, 32, 0.06);
    }}
    .hero-card {{
      padding: 24px;
    }}
    .section {{
      padding: 20px;
      margin-top: 18px;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{
      font-size: 2.2rem;
      letter-spacing: -0.03em;
      margin-bottom: 8px;
    }}
    .eyebrow {{
      color: var(--accent);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 0.75rem;
      margin-bottom: 12px;
    }}
    .subtext {{
      color: var(--muted);
      margin-top: 10px;
      line-height: 1.5;
    }}
    .summary-grid, .drivers-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }}
    .kpi {{
      padding: 18px;
    }}
    .label {{
      color: var(--muted);
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .value {{
      font-size: 1.9rem;
      font-weight: 700;
      margin-top: 8px;
    }}
    .sub, .meta {{
      color: var(--muted);
      font-size: 0.9rem;
      margin-top: 6px;
    }}
    .variance, .metric {{
      margin-top: 12px;
      font-weight: 700;
    }}
    .pos {{ color: var(--good); }}
    .neg {{ color: var(--bad); }}
    .driver {{
      padding: 18px;
    }}
    .driver p {{
      margin-top: 10px;
      line-height: 1.45;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 0.95rem;
    }}
    th, td {{
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
    }}
    th {{
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    ul {{
      margin: 12px 0 0;
      padding-left: 18px;
      line-height: 1.55;
    }}
    .pill {{
      display: inline-block;
      margin-left: 8px;
      padding: 2px 8px;
      border-radius: 999px;
      background: #e9efe7;
      color: var(--accent);
      font-size: 0.8rem;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #f7f3ea;
      border-radius: 12px;
      padding: 14px;
      margin-top: 10px;
      border: 1px solid var(--line);
      font-size: 0.85rem;
      line-height: 1.5;
    }}
    @media (max-width: 900px) {{
      .hero, .summary-grid, .drivers-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="hero-card">
        <div class="eyebrow">Monthly CFO Variance Studio</div>
        <h1>{_escape_html(result.entity)} - { _escape_html(result.period) }</h1>
        <p class="subtext">{_escape_html(result.ceo_narrative)}</p>
      </div>
      <div class="hero-card">
        <div class="eyebrow">Materiality</div>
        <p><strong>Mode:</strong> {_escape_html(result.materiality_mode)}</p>
        <p class="subtext">Abs threshold {_fmt_currency(result.materiality_threshold_abs)} | Pct threshold {result.materiality_threshold_pct:.1%}</p>
        <p class="subtext">Visible drivers: {result.shown_driver_count}</p>
      </div>
    </section>

    <section class="section">
      <h2>KPI Summary</h2>
      <div class="summary-grid">
        {kpi_cards}
      </div>
    </section>

    <section class="section">
      <h2>Visible Drivers</h2>
      <table>
        <thead>
          <tr>
            <th>Driver</th>
            <th>Category</th>
            <th>Actual</th>
            <th>Budget</th>
            <th>Variance</th>
            <th>Variance %</th>
          </tr>
        </thead>
        <tbody>
          {visible_rows}
        </tbody>
      </table>
      {other_bucket}
    </section>

    <section class="section">
      <h2>Top Drivers</h2>
      <div class="drivers-grid">
        {top_driver_blocks}
      </div>
    </section>

    <section class="section">
      <h2>Executive Summary</h2>
      <ul>{exec_bullets}</ul>
    </section>

    <section class="section">
      <h2>Risks</h2>
      <ul>{risks}</ul>
    </section>

    <section class="section">
      <h2>Opportunities</h2>
      <ul>{opportunities}</ul>
    </section>

    <section class="section">
      <h2>Suggested Actions</h2>
      <ul>{actions}</ul>
    </section>

    <section class="section">
      <h2>Audit Trail</h2>
      <ul>{audit_items}</ul>
    </section>

    {session_block}
  </div>
</body>
</html>
"""


def _to_float(value: str) -> float:
    value = value.replace(",", "").strip()
    return float(value)


def _aggregate_drivers(rows: Iterable[VarianceRow], *, group_by: str) -> List[VarianceDriver]:
    if group_by not in {"account", "department"}:
        raise ValueError("group_by must be 'account' or 'department'")
    aggregates: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = row.account if group_by == "account" else row.department
        bucket = aggregates.setdefault(
            key,
            {
                "actual": 0.0,
                "budget": 0.0,
                "category": row.category,
            },
        )
        bucket["actual"] += row.actual
        bucket["budget"] += row.budget
    drivers: List[VarianceDriver] = []
    for key, bucket in aggregates.items():
        variance = bucket["actual"] - bucket["budget"]
        variance_pct = variance / abs(bucket["budget"]) if bucket["budget"] else 0.0
        category = bucket["category"]
        insight = _driver_insight(key, variance, variance_pct, category)
        recommendation = _driver_recommendation(key, variance, category)
        drivers.append(
            VarianceDriver(
                driver_name=key,
                actual=bucket["actual"],
                budget=bucket["budget"],
                variance=variance,
                variance_pct=variance_pct,
                category=category,
                insight=insight,
                recommendation=recommendation,
            )
        )
    return drivers


def _build_kpis(rows: Iterable[VarianceRow]) -> List[VarianceKPI]:
    revenue_actual = sum(row.actual for row in rows if row.category == "Revenue")
    revenue_budget = sum(row.budget for row in rows if row.category == "Revenue")
    cogs_actual = sum(row.actual for row in rows if row.category == "COGS")
    cogs_budget = sum(row.budget for row in rows if row.category == "COGS")
    opex_actual = sum(row.actual for row in rows if row.category == "OPEX")
    opex_budget = sum(row.budget for row in rows if row.category == "OPEX")
    metrics = [
        ("Revenue", revenue_actual, revenue_budget),
        ("Gross Margin", revenue_actual - cogs_actual, revenue_budget - cogs_budget),
        ("EBITDA", revenue_actual - cogs_actual - opex_actual, revenue_budget - cogs_budget - opex_budget),
    ]
    return [
        VarianceKPI(
            label=label,
            actual=actual,
            budget=budget,
            variance=actual - budget,
            variance_pct=(actual - budget) / abs(budget) if budget else 0.0,
        )
        for label, actual, budget in metrics
    ]


def _auto_materiality(drivers: List[VarianceDriver], target_n: int = 16) -> tuple[float, float, int]:
    if not drivers:
        return 0.0, 0.0, 0
    abs_var_list = sorted((abs(driver.variance) for driver in drivers), reverse=True)
    abs_pct_list = sorted((abs(driver.variance_pct) for driver in drivers), reverse=True)
    idx = min(target_n - 1, len(abs_var_list) - 1)
    abs_threshold = max(abs_var_list[idx] * 0.95, 0.0)
    pct_threshold = max(abs_pct_list[idx] * 0.95, 0.0)
    shown_count = sum(
        1 for driver in drivers if abs(driver.variance) >= abs_threshold and abs(driver.variance_pct) >= pct_threshold
    )
    return abs_threshold, pct_threshold, shown_count


def _apply_materiality(
    drivers: List[VarianceDriver],
    *,
    abs_threshold: float,
    pct_threshold: float,
) -> tuple[List[VarianceDriver], Optional[VarianceBucket]]:
    visible: List[VarianceDriver] = []
    hidden: List[VarianceDriver] = []
    for driver in sorted(drivers, key=lambda item: abs(item.variance), reverse=True):
        if abs(driver.variance) >= abs_threshold and abs(driver.variance_pct) >= pct_threshold:
            visible.append(driver)
        else:
            hidden.append(driver)
    other_bucket: Optional[VarianceBucket] = None
    if hidden:
        actual = sum(item.actual for item in hidden)
        budget = sum(item.budget for item in hidden)
        variance = sum(item.variance for item in hidden)
        variance_pct = variance / abs(budget) if budget else 0.0
        other_bucket = VarianceBucket(
            label="Other",
            actual=actual,
            budget=budget,
            variance=variance,
            variance_pct=variance_pct,
            count=len(hidden),
        )
    return visible, other_bucket


def _data_quality_checks(rows: Iterable[VarianceRow]) -> List[str]:
    warnings: List[str] = []
    for row in rows:
        if not row.account:
            warnings.append("missing account value")
        if row.budget == 0:
            warnings.append(f"zero budget on {row.account}")
        if abs(row.actual) > 0 and abs(row.budget) > 0 and abs(row.actual - row.budget) > abs(row.budget) * 2:
            warnings.append(f"extreme variance detected on {row.account}")
    return _dedupe_preserve_order(warnings)


def _driver_insight(name: str, variance: float, variance_pct: float, category: str) -> str:
    direction = "above" if variance >= 0 else "below"
    if category == "Revenue":
        return f"{name} is **{abs(variance):,.0f} {direction} budget**, which is the clearest revenue-side movement in the current month."
    if category == "COGS":
        return f"{name} is **{abs(variance):,.0f} {direction} budget**, creating a visible cost pressure on gross margin."
    return f"{name} is **{abs(variance):,.0f} {direction} budget**, making it one of the largest operating expense drivers this month."


def _driver_recommendation(name: str, variance: float, category: str) -> str:
    if category == "Revenue":
        return f"Reconcile the commercial pipeline and mix assumptions behind {name} before locking the board narrative."
    if category == "COGS":
        return f"Review unit cost, supplier, and mix movements behind {name} and confirm whether the variance is structural or temporary."
    return f"Validate the owner, timing, and recurrence of {name} before finalizing any management action or escalation."


def _build_ceo_narrative(drivers: List[VarianceDriver], kpis: List[VarianceKPI]) -> str:
    if not drivers:
        return "No material drivers were identified from the uploaded file."
    revenue = next((item for item in kpis if item.label == "Revenue"), None)
    ebitda = next((item for item in kpis if item.label == "EBITDA"), None)
    driver_names = ", ".join(driver.driver_name for driver in drivers[:3])
    revenue_text = (
        f"Revenue is {revenue.variance:,.0f} versus budget"
        if revenue
        else "Revenue movement is included in the uploaded file"
    )
    ebitda_text = (
        f"and EBITDA is {ebitda.variance:,.0f} versus budget"
        if ebitda
        else "and profitability movement is reflected in the KPI set"
    )
    return (
        f"The month is being driven primarily by {driver_names}. {revenue_text}, {ebitda_text}. "
        f"The immediate focus should be to confirm whether these variances reflect timing, mix, or structural movement before the story is finalized for the board or CEO."
    )[:420]


def _build_exec_summary_bullets(drivers: List[VarianceDriver], kpis: List[VarianceKPI]) -> List[str]:
    bullets: List[str] = []
    for driver in drivers[:3]:
        direction = "favorable" if driver.variance > 0 and driver.category == "Revenue" else "unfavorable"
        if driver.category != "Revenue":
            direction = "unfavorable" if driver.variance > 0 else "favorable"
        bullets.append(
            f"{driver.driver_name} is one of the largest movements at {driver.variance:,.0f} versus budget, creating a {direction} signal that should anchor the monthly narrative."
        )
    ebitda = next((item for item in kpis if item.label == "EBITDA"), None)
    if ebitda:
        bullets.append(
            f"EBITDA is {ebitda.variance:,.0f} versus budget, so the final commentary should connect driver-level movement back to bottom-line impact."
        )
    return bullets[:4]


def _build_risks(drivers: List[VarianceDriver], warnings: List[str]) -> List[NarrativeItem]:
    risks: List[NarrativeItem] = []
    for driver in drivers[:2]:
        if driver.category == "OPEX" and driver.variance > 0:
            risks.append(
                NarrativeItem(
                    text=f"{driver.driver_name} is pressuring spend control and could weaken confidence in cost discipline if left unexplained.",
                    severity="high" if abs(driver.variance_pct) >= 0.25 else "medium",
                )
            )
        elif driver.category == "Revenue" and driver.variance < 0:
            risks.append(
                NarrativeItem(
                    text=f"{driver.driver_name} is below budget and may indicate softness in mix, timing, or execution quality.",
                    severity="high" if abs(driver.variance_pct) >= 0.15 else "medium",
                )
            )
    if warnings:
        risks.append(
            NarrativeItem(
                text="Data quality warnings were detected, so the narrative should flag assumptions rather than imply complete certainty.",
                severity="medium",
            )
        )
    return risks[:3]


def _build_opportunities(drivers: List[VarianceDriver]) -> List[NarrativeItem]:
    items: List[NarrativeItem] = []
    for driver in drivers:
        if driver.category == "Revenue" and driver.variance > 0:
            items.append(
                NarrativeItem(
                    text=f"{driver.driver_name} is outperforming budget and can be used to identify repeatable commercial tactics or mix advantages.",
                    size_hint=f"{driver.variance:,.0f}",
                )
            )
        elif driver.category != "Revenue" and driver.variance < 0:
            items.append(
                NarrativeItem(
                    text=f"{driver.driver_name} is below budget and may represent a sustainable efficiency gain if it is structural rather than timing-driven.",
                    size_hint=f"{abs(driver.variance):,.0f}",
                )
            )
    return items[:3]


def _build_suggested_actions(drivers: List[VarianceDriver]) -> List[NarrativeItem]:
    actions: List[NarrativeItem] = []
    for driver in drivers[:3]:
        if driver.category == "Revenue":
            actions.append(
                NarrativeItem(
                    text=f"Confirm the commercial explanation behind {driver.driver_name} and decide whether it should change the next forecast cut.",
                    owner_hint="Revenue / FP&A",
                    expected_impact_hint="forecast quality",
                )
            )
        else:
            actions.append(
                NarrativeItem(
                    text=f"Validate whether {driver.driver_name} is timing, scope, or a true structural movement before locking management commentary.",
                    owner_hint="Department owner / FP&A",
                    expected_impact_hint="variance credibility",
                )
            )
    return actions


def _build_audit_trail(
    drivers: List[VarianceDriver],
    kpis: List[VarianceKPI],
    other_bucket: Optional[VarianceBucket],
) -> List[AuditTrailItem]:
    trail: List[AuditTrailItem] = []
    for driver in drivers[:3]:
        trail.append(
            AuditTrailItem(
                statement=f"{driver.driver_name} is included because it ranks among the largest absolute budget variances.",
                linked_numbers=[
                    {"label": "actual", "value": round(driver.actual, 2)},
                    {"label": "budget", "value": round(driver.budget, 2)},
                    {"label": "variance", "value": round(driver.variance, 2)},
                ],
            )
        )
    ebitda = next((item for item in kpis if item.label == "EBITDA"), None)
    if ebitda:
        trail.append(
            AuditTrailItem(
                statement="The topline driver discussion should reconcile back to EBITDA movement.",
                linked_numbers=[
                    {"label": "ebitda_actual", "value": round(ebitda.actual, 2)},
                    {"label": "ebitda_budget", "value": round(ebitda.budget, 2)},
                    {"label": "ebitda_variance", "value": round(ebitda.variance, 2)},
                ],
            )
        )
    if other_bucket:
        trail.append(
            AuditTrailItem(
                statement="Non-material drivers are aggregated into Other for readability while preserving total movement.",
                linked_numbers=[
                    {"label": "other_variance", "value": round(other_bucket.variance, 2)},
                    {"label": "other_count", "value": other_bucket.count},
                ],
            )
        )
    return trail


def _slugify(text: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _fmt_currency(value: float) -> str:
    return f"${value:,.0f}"


def _escape_html(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
