"""Month-over-Month variance analysis — tracks period-over-period deltas with CHP hardening."""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from cme.chp.models import DecisionCase, Dossier, FoundationAttack, FoundationDisclosure
from cme.finance.variance_studio import (
    VarianceKPI,
    NarrativeItem,
    AuditTrailItem,
    VarianceRow,
    VarianceDriver,
    VarianceBucket,
    _to_float,
    _dedupe_preserve_order,
    _escape_html,
    _fmt_currency,
)


MOM_REQUIRED_COLUMNS = {"period", "entity", "department", "account", "category", "actual"}


@dataclass
class MoMVarianceResult:
    """Result of a month-over-month variance comparison."""

    entity: str
    base_period: str
    compare_period: str
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
    trend_summary: str = ""
    data_quality_warnings: List[str] = field(default_factory=list)
    abs_threshold: float = 0.0
    pct_threshold: float = 0.0
    shown_driver_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "base_period": self.base_period,
            "compare_period": self.compare_period,
            "kpis": [k.to_dict() for k in self.kpis],
            "drivers": [d.to_dict() for d in self.drivers],
            "visible_drivers": [d.to_dict() for d in self.visible_drivers],
            "other_bucket": self.other_bucket.to_dict() if self.other_bucket else None,
            "spotlight_driver": self.spotlight_driver.to_dict() if self.spotlight_driver else None,
            "exec_summary_bullets": self.exec_summary_bullets,
            "risks": [r.to_dict() for r in self.risks],
            "opportunities": [o.to_dict() for o in self.opportunities],
            "suggested_actions": [a.to_dict() for a in self.suggested_actions],
            "audit_trail": [a.to_dict() for a in self.audit_trail],
            "trend_summary": self.trend_summary,
            "data_quality_warnings": self.data_quality_warnings,
            "abs_threshold": self.abs_threshold,
            "pct_threshold": self.pct_threshold,
            "shown_driver_count": self.shown_driver_count,
        }


def load_mom_csv(path: str | Path) -> tuple[List[VarianceRow], List[str]]:
    rows: List[VarianceRow] = []
    warnings: List[str] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = MOM_REQUIRED_COLUMNS - {name.strip().lower() for name in (reader.fieldnames or [])}
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
        for idx, raw in enumerate(reader, start=2):
            try:
                actual = _to_float(raw["actual"])
                budget = _to_float(raw.get("budget", "0"))
            except Exception as exc:
                warnings.append(f"row {idx}: invalid numeric values ({exc})")
                continue
            category = raw["category"].strip()
            if category not in {"Revenue", "COGS", "OPEX"}:
                warnings.append(f"row {idx}: unexpected category '{category}'")
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


def _aggregate_drivers_for_period(rows: List[VarianceRow]) -> Dict[str, float]:
    """Aggregate actual amounts by account for a set of rows."""
    aggregates: Dict[str, float] = {}
    for row in rows:
        aggregates[row.account] = aggregates.get(row.account, 0.0) + row.actual
    return aggregates


def _aggregate_kpis_for_period(rows: List[VarianceRow]) -> Dict[str, float]:
    rev = sum(r.actual for r in rows if r.category == "Revenue")
    cogs = sum(r.actual for r in rows if r.category == "COGS")
    opex = sum(r.actual for r in rows if r.category == "OPEX")
    return {"Revenue": rev, "Gross Margin": rev - cogs, "EBITDA": rev - cogs - opex}


def analyze_mom_variance(
    rows: Iterable[VarianceRow],
    *,
    entity: str | None = None,
    base_period: str | None = None,
    compare_period: str | None = None,
) -> MoMVarianceResult:
    rows_list = list(rows)
    if not rows_list:
        raise ValueError("no rows available for analysis")

    periods = sorted(set(r.period for r in rows_list))
    if len(periods) < 2:
        raise ValueError(f"need at least 2 periods for MoM analysis; found {len(periods)}: {periods}")

    entity = entity or rows_list[0].entity
    if base_period is None:
        base_period = periods[-1]  # most recent is base
    if compare_period is None:
        # compare to the period before base
        base_idx = periods.index(base_period)
        compare_period = periods[base_idx - 1] if base_idx > 0 else periods[0]

    base_rows = [r for r in rows_list if r.period == base_period and r.entity == entity]
    comp_rows = [r for r in rows_list if r.period == compare_period and r.entity == entity]
    if not base_rows or not comp_rows:
        raise ValueError(f"missing rows for periods: base={base_period} compare={compare_period}")

    # Build KPI comparison
    base_kpis = _aggregate_kpis_for_period(base_rows)
    comp_kpis = _aggregate_kpis_for_period(comp_rows)
    kpis = [
        VarianceKPI(
            label=label,
            actual=base_kpis[label],
            budget=comp_kpis[label],
            variance=base_kpis[label] - comp_kpis[label],
            variance_pct=(base_kpis[label] - comp_kpis[label]) / abs(comp_kpis[label]) if comp_kpis[label] else 0.0,
        )
        for label in ["Revenue", "Gross Margin", "EBITDA"]
    ]

    # Build driver-level comparison
    base_driver_actuals = _aggregate_drivers_for_period(base_rows)
    comp_driver_actuals = _aggregate_drivers_for_period(comp_rows)
    all_accounts = set(base_driver_actuals.keys()) | set(comp_driver_actuals.keys())

    drivers: List[VarianceDriver] = []
    for account in all_accounts:
        ba = base_driver_actuals.get(account, 0.0)
        ca = comp_driver_actuals.get(account, 0.0)
        variance = ba - ca
        variance_pct = variance / abs(ca) if ca else 0.0
        # Determine category from whichever period has it
        matching = [r for r in base_rows + comp_rows if r.account == account]
        category = matching[0].category if matching else "OPEX"

        direction = "above" if variance >= 0 else "below"
        if category == "Revenue":
            insight = f"{account} is **{abs(variance):,.0f} {direction} {compare_period}**, representing a clear revenue movement."
        elif category == "COGS":
            insight = f"{account} is **{abs(variance):,.0f} {direction} {compare_period}**, affecting gross margin."
        else:
            insight = f"{account} is **{abs(variance):,.0f} {direction} {compare_period}**, a notable operating expense shift."

        if category == "Revenue":
            recommendation = f"Determine whether this {direction}-budget movement in {account} is repeatable or one-off before forecasting."
        elif category == "COGS":
            recommendation = f"Analyze unit cost or supplier mix changes in {account} to confirm if the trend is structural."
        else:
            recommendation = f"Engage the department owner for {account} to validate whether the trend is timing, scope, or structural."

        drivers.append(VarianceDriver(
            driver_name=account,
            actual=ba,
            budget=ca,
            variance=variance,
            variance_pct=variance_pct,
            category=category,
            insight=insight,
            recommendation=recommendation,
        ))

    # Sort by absolute variance
    drivers.sort(key=lambda d: abs(d.variance), reverse=True)

    # Apply materiality (top 5 absolute)
    top5 = drivers[:5]
    visible = drivers[:max(3, len(drivers) - 2)]
    hidden = drivers[len(visible):]
    other_bucket = None
    if hidden:
        other_bucket = VarianceBucket(
            label="Other (MoM)",
            actual=sum(h.actual for h in hidden),
            budget=sum(h.budget for h in hidden),
            variance=sum(h.variance for h in hidden),
            variance_pct=(
                sum(h.variance for h in hidden) / abs(sum(h.budget for h in hidden))
                if sum(h.budget for h in hidden) else 0.0
            ),
            count=len(hidden),
        )

    spotlight = top5[0] if top5 else None

    # Build narrative
    trend_direction = "improving" if kpis[0].variance > 0 else "declining"
    trend_note = (
        f"Revenue moved from {comp_kpis['Revenue']:,.0f} ({compare_period}) to "
        f"{base_kpis['Revenue']:,.0f} ({base_period}), a trend that is {trend_direction}. "
        f"Top drivers: {', '.join(d.driver_name for d in top5[:3])}."
    )

    exec_bullets = [
        f"{d.driver_name} moved by {d.variance:,.0f} between {compare_period} and {base_period}, "
        f"the largest {d.category.lower()} trend in this comparison."
        for d in top5[:3]
    ]
    if kpis[2]:  # EBITDA
        exec_bullets.append(
            f"EBITDA shifted by {kpis[2].variance:,.0f} between periods, "
            f"linking top-line movement to bottom-line impact."
        )

    risks = [
        NarrativeItem(
            text=f"{d.driver_name} {'grew' if d.variance > 0 else 'declined'} by {abs(d.variance):,.0f} — "
                 f"without driver attribution, the trend narrative is incomplete.",
            severity="high" if abs(d.variance_pct) >= 0.2 else "medium",
        )
        for d in top5[:2] if abs(d.variance) > 0
    ]

    opportunities = [
        NarrativeItem(
            text=f"{d.driver_name} {'outperformance' if d.variance > 0 and d.category == 'Revenue' else 'reduction'} "
                 f"of {abs(d.variance):,.0f} may reveal structural advantages.",
            size_hint=f"{abs(d.variance):,.0f}",
        )
        for d in top5[:2] if d.category == "Revenue" or d.variance < 0
    ]

    suggested_actions = [
        NarrativeItem(
            text=f"Root-cause the {d.driver_name} movement: confirm whether it repeats or reverts in the next period.",
            owner_hint="FP&A",
            expected_impact_hint="forecast accuracy",
        )
        for d in top5[:3]
    ]

    audit_trail = [
        AuditTrailItem(
            statement=f"{d.driver_name} selected as a top MoM driver with movement of {d.variance:,.0f} from {compare_period} to {base_period}.",
            linked_numbers=[
                {"label": f"{base_period}", "value": round(d.actual, 2)},
                {"label": f"{compare_period}", "value": round(d.budget, 2)},
                {"label": "delta", "value": round(d.variance, 2)},
            ],
        )
        for d in top5[:3]
    ]

    warnings = _dedupe_preserve_order(
        [] if abs(comp_kpis.get("Revenue", 0)) > 0 else ["zero base-period revenue for KPI computation"]
    )

    return MoMVarianceResult(
        entity=entity,
        base_period=base_period,
        compare_period=compare_period,
        kpis=kpis,
        drivers=top5,
        visible_drivers=visible,
        other_bucket=other_bucket,
        spotlight_driver=spotlight,
        exec_summary_bullets=exec_bullets,
        risks=risks,
        opportunities=opportunities,
        suggested_actions=suggested_actions,
        audit_trail=audit_trail,
        trend_summary=trend_note,
        data_quality_warnings=warnings,
        shown_driver_count=len(visible),
    )


def build_mom_variance_case(
    result: MoMVarianceResult,
    *,
    owner: str = "cfo",
    origin_system: str = "Claude",
    origin_model: str = "GPT-5.4",
    partner_system: str = "Partner",
    partner_model: str = "GPT-5-equivalent",
) -> tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    decision_id = f"mom-variance-{result.entity}-{result.base_period}-vs-{result.compare_period}"
    decision_id = "".join(ch.lower() if ch.isalnum() else "-" for ch in decision_id).strip("-")[:50]
    top_driver_names = [d.driver_name for d in result.drivers[:3]]
    dossier = Dossier(
        core_problem=f"Identify and validate month-over-month performance drivers for {result.entity}: {result.compare_period} → {result.base_period}.",
        goal_state=[
            f"Top MoM drivers ranked by absolute movement",
            f"Trend narrative is grounded in numeric deltas",
            f"Reversible vs structural categorization documented",
        ],
        current_state=[
            f"Comparing {result.compare_period} to {result.base_period}",
            f"{len(result.drivers)} accounts with measurable movement",
        ],
        constraints=[
            "Do not over-attribute direction until confirmed by root cause",
            "Movement magnitude must drive ranking, not opinion",
        ],
        unknowns=[
            "External market factors not present in the uploaded file",
            "Operational timing decisions that may reverse next month",
        ],
        scope=["Driver ranking and categorization", "Trend narrative hardening"],
        origin_direction=[
            "Prefer delta-grounded statements over qualitative speculation",
        ],
        structural_vulnerabilities=[
            "MoM deltas can amplify timing shifts into structural-sounding trends",
        ],
    )
    case = DecisionCase(
        decision_id=decision_id,
        title=f"MoM variance review: {result.entity} {result.compare_period} → {result.base_period}",
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
            f"Base period ({result.base_period}) and compare period ({result.compare_period}) are comparable in business activity",
            "Account-level aggregation is the right grain for identifying trends",
            "No major reclasses or accounting adjustments occurred between periods",
        ],
        invalidation_conditions=[
            "Seasonal activity skews the comparison",
            "One-time items in either period distort the trend",
        ],
        key_vulnerability="MoM variance can be mistaken for a trend when it is actually timing, seasonal, or one-off.",
    )
    score = 80
    attack = FoundationAttack(
        assumption_attacks=[
            f"{result.base_period} and {result.compare_period} may not be comparable if business mix changed.",
            "Account-level aggregation may mask meaningful departmental shifts.",
            "Reclasses, accrual corrections, or cut-off timing can distort period deltas.",
        ],
        invalidation_exploitation=[
            "A seasonal spike in either period can invert the trend interpretation.",
            "One-time credits or charges in either period distort delta rankings.",
        ],
        vulnerability_strike="The highest risk is interpreting a timing delta as a structural trend.",
        foundation_score=score,
        attack_summary=f"MoM analysis provides useful directional signal, but each delta should be classified as timing, seasonal, or structural before locking.",
    )
    dossier.foundation_score = score
    dossier.prior_round_summary = [f"Top MoM drivers: {', '.join(top_driver_names)}"] if top_driver_names else []
    return case, disclosure, attack


def render_mom_variance_markdown(result: MoMVarianceResult) -> str:
    lines = [
        f"# Month-over-Month Variance Analysis",
        f"**Entity:** {result.entity}",
        f"**Period:** {result.compare_period} → {result.base_period}",
        "",
        "## Trend Summary",
        result.trend_summary,
        "",
        "## KPI Comparison",
    ]
    for kpi in result.kpis:
        lines.append(
            f"- {kpi.label}: {_fmt_currency(kpi.actual)} ({result.base_period}) vs "
            f"{_fmt_currency(kpi.budget)} ({result.compare_period}) — "
            f"delta {_fmt_currency(kpi.variance)} ({kpi.variance_pct:.1%})"
        )
    lines.append("")
    lines.append("## Top Drivers (by absolute movement)")
    for idx, driver in enumerate(result.drivers, start=1):
        lines.append(
            f"{idx}. {driver.driver_name} | {result.base_period}={_fmt_currency(driver.actual)} | "
            f"{result.compare_period}={_fmt_currency(driver.budget)} | "
            f"delta={_fmt_currency(driver.variance)} ({driver.variance_pct:.1%})"
        )
        lines.append(f"   Insight: {driver.insight}")
        lines.append(f"   Recommendation: {driver.recommendation}")
    if result.other_bucket:
        lines.append(
            f"\nOther bucket: {_fmt_currency(result.other_bucket.variance)} ({result.other_bucket.variance_pct:.1%}) "
            f"across {result.other_bucket.count} items"
        )
    if result.exec_summary_bullets:
        lines.extend(["", "## Executive Summary"] + [f"- {b}" for b in result.exec_summary_bullets])
    if result.risks:
        lines.extend(["", "## Risks"] + [f"- {r.text} [{r.severity}]" for r in result.risks])
    if result.opportunities:
        lines.extend(["", "## Opportunities"] + [f"- {o.text} [{o.size_hint}]" for o in result.opportunities])
    if result.suggested_actions:
        lines.extend(["", "## Suggested Actions"] + [
            f"- {a.text} | owner={a.owner_hint} | impact={a.expected_impact_hint}"
            for a in result.suggested_actions
        ])
    if result.audit_trail:
        def _fmt_audit(n: dict) -> str:
            return f"{n['label']}={n['value']}"
        lines.extend(["", "## Audit Trail"] + [
            f"- {a.statement} :: {'; '.join(_fmt_audit(n) for n in a.linked_numbers)}"
            for a in result.audit_trail
        ])
    return "\n".join(lines)


def render_mom_variance_html(result: MoMVarianceResult, *, session_summary: str = "") -> str:
    kpi_cards = "\n".join(
        f"""
        <div class="card kpi">
          <div class="label">{_escape_html(kpi.label)}</div>
          <div class="value">{_fmt_currency(kpi.variance)}</div>
          <div class="sub">{result.base_period}: {_fmt_currency(kpi.actual)} | {result.compare_period}: {_fmt_currency(kpi.budget)}</div>
          <div class="variance {'neg' if kpi.variance < 0 else 'pos'}">{kpi.variance_pct:.1%} delta</div>
        </div>
        """
        for kpi in result.kpis
    )

    visible_rows = "\n".join(
        f"""
        <tr>
          <td>{_escape_html(d.driver_name)}</td>
          <td>{_escape_html(d.category)}</td>
          <td>{_fmt_currency(d.actual)}</td>
          <td>{_fmt_currency(d.budget)}</td>
          <td class="{'neg' if d.variance < 0 else 'pos'}">{_fmt_currency(d.variance)}</td>
          <td>{d.variance_pct:.1%}</td>
        </tr>
        """
        for d in result.visible_drivers
    )

    driver_blocks = "\n".join(
        f"""
        <div class="card driver">
          <h3>{_escape_html(d.driver_name)}</h3>
          <p class="metric {'neg' if d.variance < 0 else 'pos'}">{_fmt_currency(d.variance)} ({d.variance_pct:.1%})</p>
          <p>{_escape_html(d.insight)}</p>
          <p><strong>Recommendation:</strong> {_escape_html(d.recommendation)}</p>
        </div>
        """
        for d in result.drivers[:3]
    )

    exec_bullets = "".join(f"<li>{_escape_html(b)}</li>" for b in result.exec_summary_bullets)
    risks = "".join(f"<li><strong>{_escape_html(r.severity or 'info')}:</strong> {_escape_html(r.text)}</li>" for r in result.risks)
    def _pill(v: str | None) -> str:
        return f' <span class="pill">{_escape_html(v)}</span>' if v else ''
    opportunities = "".join(f"<li>{_escape_html(o.text)}{_pill(o.size_hint)}</li>" for o in result.opportunities)
    actions = "".join(f"<li>{_escape_html(a.text)} <span class=\"meta\">owner={_escape_html(a.owner_hint)}</span></li>" for a in result.suggested_actions)
    def _audit_link(n: dict) -> str:
        return f"{_escape_html(str(n['label']))}={_escape_html(str(n['value']))}"
    audit_items = "".join(
        f"<li>{_escape_html(a.statement)} :: " +
        ", ".join(_audit_link(n) for n in a.linked_numbers) +
        "</li>"
        for a in result.audit_trail
    )

    other_html = ""
    if result.other_bucket:
        other_html = f"<div class='card'><h3>Other Bucket</h3><p>{_fmt_currency(result.other_bucket.variance)} ({result.other_bucket.variance_pct:.1%}) across {result.other_bucket.count} items</p></div>"

    session_block = (
        f"<section class='section'><h2>CHP Session</h2><pre>{_escape_html(session_summary)}</pre></section>"
        if session_summary else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MoM Variance Studio</title>
  <style>
    :root {{ --bg: #f5f1e8; --panel: #fffdf8; --ink: #1f2520; --muted: #657166; --line: #d8cfbf; --accent: #134e4a; --warn: #b45309; --good: #166534; --bad: #b91c1c; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Avenir Next","Segoe UI",sans-serif; background: linear-gradient(180deg,#f1eadb 0%,#f7f4ed 100%); color: var(--ink); }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px 56px; }}
    .hero, .summary-grid, .drivers-grid {{ display: grid; gap: 20px; }}
    .hero {{ grid-template-columns: 2fr 1fr; align-items: start; margin-bottom: 24px; }}
    .summary-grid {{ grid-template-columns: repeat(3,1fr); }}
    .drivers-grid {{ grid-template-columns: repeat(3,1fr); }}
    .hero-card, .card, .section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; box-shadow: 0 12px 32px rgba(31,37,32,0.06); }}
    .hero-card {{ padding: 24px; }}
    .section {{ padding: 20px; margin-top: 18px; }}
    h1,h2,h3,p {{ margin: 0; }}
    h1 {{ font-size: 2.2rem; letter-spacing: -0.03em; margin-bottom: 8px; }}
    .eyebrow {{ color: var(--accent); font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; font-size: 0.75rem; margin-bottom: 12px; }}
    .subtext {{ color: var(--muted); margin-top: 10px; line-height: 1.5; }}
    .kpi {{ padding: 18px; }}
    .label {{ color: var(--muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    .value {{ font-size: 1.9rem; font-weight: 700; margin-top: 8px; }}
    .sub, .meta {{ color: var(--muted); font-size: 0.9rem; margin-top: 6px; }}
    .variance, .metric {{ margin-top: 12px; font-weight: 700; }}
    .pos {{ color: var(--good); }}
    .neg {{ color: var(--bad); }}
    .driver {{ padding: 18px; }}
    .driver p {{ margin-top: 10px; line-height: 1.45; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 0.95rem; }}
    th, td {{ padding: 12px 10px; border-bottom: 1px solid var(--line); text-align: left; }}
    th {{ color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    ul {{ margin: 12px 0 0; padding-left: 18px; line-height: 1.55; }}
    .pill {{ display: inline-block; margin-left: 8px; padding: 2px 8px; border-radius: 999px; background: #e9efe7; color: var(--accent); font-size: 0.8rem; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #f7f3ea; border-radius: 12px; padding: 14px; margin-top: 10px; border: 1px solid var(--line); font-size: 0.85rem; line-height: 1.5; }}
    @media (max-width:900px) {{ .hero,.summary-grid,.drivers-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="hero-card">
        <div class="eyebrow">Month-over-Month Variance Studio</div>
        <h1>{_escape_html(result.entity)} — {_escape_html(result.compare_period)} → {_escape_html(result.base_period)}</h1>
        <p class="subtext">{_escape_html(result.trend_summary)}</p>
      </div>
      <div class="hero-card">
        <div class="eyebrow">Visible Drivers</div>
        <p>{result.shown_driver_count} of {len(result.drivers)}</p>
        <p class="subtext">Spotlight: {_escape_html(result.spotlight_driver.driver_name) if result.spotlight_driver else 'N/A'}</p>
      </div>
    </section>

    <section class="section">
      <h2>KPI Comparison</h2>
      <div class="summary-grid">{kpi_cards}</div>
    </section>

    <section class="section">
      <h2>Driver Movements</h2>
      <table><thead><tr><th>Driver</th><th>Cat</th><th>{_escape_html(result.base_period)}</th><th>{_escape_html(result.compare_period)}</th><th>Delta</th><th>Δ%</th></tr></thead>
      <tbody>{visible_rows}</tbody></table>
      {other_html}
    </section>

    <section class="section">
      <h2>Top Drivers</h2>
      <div class="drivers-grid">{driver_blocks}</div>
    </section>

    <section class="section"><h2>Executive Summary</h2><ul>{exec_bullets}</ul></section>
    <section class="section"><h2>Risks</h2><ul>{risks}</ul></section>
    <section class="section"><h2>Opportunities</h2><ul>{opportunities}</ul></section>
    <section class="section"><h2>Suggested Actions</h2><ul>{actions}</ul></section>
    <section class="section"><h2>Audit Trail</h2><ul>{audit_items}</ul></section>
    {session_block}
  </div>
</body>
</html>"""
