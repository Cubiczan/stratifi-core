"""Actual-vs-Forecast variance analysis — compares actuals against a forecast column with CHP hardening."""
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
    VarianceDriver,
    VarianceBucket,
    _to_float,
    _dedupe_preserve_order,
    _escape_html,
    _fmt_currency,
)


FORECAST_REQUIRED_COLUMNS = {"period", "entity", "department", "account", "category", "actual", "forecast"}


@dataclass
class VarianceRowWithForecast:
    """A single variance data row that includes a forecast column."""
    period: str
    entity: str
    department: str
    account: str
    category: str
    actual: float
    forecast: float


@dataclass
class ForecastVarianceResult:
    """Result of an actual-vs-forecast variance analysis."""
    period: str
    entity: str
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
    forecast_accuracy_summary: str = ""
    data_quality_warnings: List[str] = field(default_factory=list)
    abs_threshold: float = 0.0
    pct_threshold: float = 0.0
    shown_driver_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "entity": self.entity,
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
            "forecast_accuracy_summary": self.forecast_accuracy_summary,
            "data_quality_warnings": self.data_quality_warnings,
            "shown_driver_count": self.shown_driver_count,
        }


def load_forecast_csv(path: str | Path) -> tuple[List[VarianceRowWithForecast], List[str]]:
    rows: List[VarianceRowWithForecast] = []
    warnings: List[str] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = FORECAST_REQUIRED_COLUMNS - {name.strip().lower() for name in (reader.fieldnames or [])}
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
        for idx, raw in enumerate(reader, start=2):
            try:
                actual = _to_float(raw["actual"])
                forecast = _to_float(raw["forecast"])
            except Exception as exc:
                warnings.append(f"row {idx}: invalid numeric values ({exc})")
                continue
            category = raw["category"].strip()
            if category not in {"Revenue", "COGS", "OPEX"}:
                warnings.append(f"row {idx}: unexpected category '{category}'")
            if forecast == 0:
                warnings.append(f"row {idx}: zero forecast for {raw['account']}")
            rows.append(VarianceRowWithForecast(
                period=raw["period"].strip(),
                entity=raw["entity"].strip(),
                department=raw["department"].strip(),
                account=raw["account"].strip(),
                category=category,
                actual=actual,
                forecast=forecast,
            ))
    return rows, _dedupe_preserve_order(warnings)


def analyze_forecast_variance(
    rows: Iterable[VarianceRowWithForecast],
    *,
    period: str | None = None,
    entity: str | None = None,
) -> ForecastVarianceResult:
    rows_list = list(rows)
    if not rows_list:
        raise ValueError("no rows available for analysis")
    entity = entity or rows_list[0].entity
    period = period or rows_list[0].period
    filtered = [r for r in rows_list if r.period == period and r.entity == entity]
    if not filtered:
        raise ValueError(f"no rows found for period={period} entity={entity}")

    # Compute KPIs
    rev_actual = sum(r.actual for r in filtered if r.category == "Revenue")
    rev_forecast = sum(r.forecast for r in filtered if r.category == "Revenue")
    cogs_actual = sum(r.actual for r in filtered if r.category == "COGS")
    cogs_forecast = sum(r.forecast for r in filtered if r.category == "COGS")
    opex_actual = sum(r.actual for r in filtered if r.category == "OPEX")
    opex_forecast = sum(r.forecast for r in filtered if r.category == "OPEX")

    kpis = [
        VarianceKPI("Revenue", rev_actual, rev_forecast, rev_actual - rev_forecast,
                     (rev_actual - rev_forecast) / abs(rev_forecast) if rev_forecast else 0.0),
        VarianceKPI("Gross Margin", rev_actual - cogs_actual, rev_forecast - cogs_forecast,
                     (rev_actual - cogs_actual) - (rev_forecast - cogs_forecast),
                     ((rev_actual - cogs_actual) - (rev_forecast - cogs_forecast)) / abs(rev_forecast - cogs_forecast) if (rev_forecast - cogs_forecast) else 0.0),
        VarianceKPI("EBITDA", rev_actual - cogs_actual - opex_actual, rev_forecast - cogs_forecast - opex_forecast,
                     (rev_actual - cogs_actual - opex_actual) - (rev_forecast - cogs_forecast - opex_forecast),
                     ((rev_actual - cogs_actual - opex_actual) - (rev_forecast - cogs_forecast - opex_forecast)) / abs(rev_forecast - cogs_forecast - opex_forecast) if (rev_forecast - cogs_forecast - opex_forecast) else 0.0),
    ]

    # Build drivers
    aggregates: Dict[str, Dict[str, float]] = {}
    for r in filtered:
        agg = aggregates.setdefault(r.account, {"actual": 0.0, "forecast": 0.0, "category": r.category})
        agg["actual"] += r.actual
        agg["forecast"] += r.forecast

    drivers: List[VarianceDriver] = []
    for name, agg in aggregates.items():
        variance = agg["actual"] - agg["forecast"]
        variance_pct = variance / abs(agg["forecast"]) if agg["forecast"] else 0.0
        category = agg["category"]
        direction = "above" if variance >= 0 else "below"
        if category == "Revenue":
            insight = f"{name} **{abs(variance):,.0f} {direction} forecast** — key revenue forecast variance."
        elif category == "COGS":
            insight = f"{name} **{abs(variance):,.0f} {direction} forecast** — cost forecast variance affecting margin."
        else:
            insight = f"{name} **{abs(variance):,.0f} {direction} forecast** — operating expense forecast deviation."
        if category == "Revenue":
            recommendation = f"Review forecast methodology for {name}: what drove the miss/beat?"
        elif category == "COGS":
            recommendation = f"Validate cost drivers in {name} to improve next forecast cycle."
        else:
            recommendation = f"Engage {name} owner to reconcile actual vs forecast variance."
        drivers.append(VarianceDriver(name, agg["actual"], agg["forecast"], variance, variance_pct, category, insight, recommendation))

    drivers.sort(key=lambda d: abs(d.variance), reverse=True)
    visible = drivers[:max(3, min(len(drivers), 6))]
    hidden = drivers[len(visible):]
    other_bucket = None
    if hidden:
        other_bucket = VarianceBucket("Other (Forecast)",
            sum(h.actual for h in hidden), sum(h.budget for h in hidden),
            sum(h.variance for h in hidden),
            sum(h.variance for h in hidden) / abs(sum(h.budget for h in hidden)) if sum(h.budget for h in hidden) else 0.0,
            len(hidden))

    top3 = drivers[:3]
    spotlight = top3[0] if top3 else None

    # Accuracy metrics
    all_actual = sum(r.actual for r in filtered)
    all_forecast = sum(r.forecast for r in filtered)
    accuracy_pct = (1 - abs(all_actual - all_forecast) / abs(all_forecast)) * 100 if all_forecast else 0.0
    accuracy_summary = (
        f"Forecast accuracy for {entity} in {period}: {accuracy_pct:.1f}%. "
        f"Total actual {_fmt_currency(all_actual)} vs forecast {_fmt_currency(all_forecast)} "
        f"(variance {_fmt_currency(all_actual - all_forecast)}). "
        f"Largest {top3[0].driver_name if top3 else 'driver'} drives the dominant variance."
    )

    exec_bullets = [
        f"Revenue: actual {_fmt_currency(rev_actual)} vs forecast {_fmt_currency(rev_forecast)} — "
        f"{'beat' if rev_actual >= rev_forecast else 'miss'} by {_fmt_currency(abs(rev_actual - rev_forecast))}."
    ]
    if top3:
        exec_bullets.append(
            f"{top3[0].driver_name} is the largest variance at {_fmt_currency(top3[0].variance)} "
            f"({top3[0].variance_pct:.1%}) and should anchor the forecast quality review."
        )

    risks = [
        NarrativeItem(
            text=f"{d.driver_name} variance of {_fmt_currency(abs(d.variance))} indicates forecast process weakness "
                 f"if this account is material.",
            severity="high" if abs(d.variance_pct) >= 0.2 else "medium",
        )
        for d in top3[:2]
    ]

    suggestions = [
        NarrativeItem(
            text=f"Root-cause the {d.driver_name} forecast variance: is it a methodology issue, timing, or a true surprise?",
            owner_hint="FP&A / Department",
            expected_impact_hint="forecast improvement",
        )
        for d in top3[:3]
    ]

    opportunities = [
        NarrativeItem(
            text=f"{d.driver_name} variance of {_fmt_currency(abs(d.variance))} is an opportunity "
                 f"to improve forecasting precision for this line item.",
            size_hint=f"{abs(d.variance):,.0f}",
        )
        for d in top3[:2]
    ]

    audit_trail = [
        AuditTrailItem(
            statement=f"{d.driver_name}: actual {_fmt_currency(d.actual)} vs forecast {_fmt_currency(d.budget)} — "
                     f"deviation of {_fmt_currency(d.variance)}.",
            linked_numbers=[
                {"label": "actual", "value": round(d.actual, 2)},
                {"label": "forecast", "value": round(d.budget, 2)},
                {"label": "variance", "value": round(d.variance, 2)},
            ],
        )
        for d in top3
    ]

    return ForecastVarianceResult(
        period=period, entity=entity, kpis=kpis, drivers=top3,
        visible_drivers=visible, other_bucket=other_bucket,
        spotlight_driver=spotlight, exec_summary_bullets=exec_bullets,
        risks=risks, opportunities=opportunities, suggested_actions=suggestions,
        audit_trail=audit_trail, forecast_accuracy_summary=accuracy_summary,
        data_quality_warnings=[], shown_driver_count=len(visible),
    )


def build_forecast_variance_case(
    result: ForecastVarianceResult,
    *,
    owner: str = "cfo",
    origin_system: str = "Claude",
    origin_model: str = "GPT-5.4",
    partner_system: str = "Partner",
    partner_model: str = "GPT-5-equivalent",
) -> tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    decision_id = f"forecast-variance-{result.entity}-{result.period}"
    decision_id = "".join(ch.lower() if ch.isalnum() else "-" for ch in decision_id).strip("-")[:50]
    top_driver_names = [d.driver_name for d in result.drivers[:3]]

    dossier = Dossier(
        core_problem=f"Evaluate forecast accuracy for {result.entity} in {result.period} by hardening actual-vs-forecast deviations through CHP.",
        goal_state=[
            "Top forecast deviations ranked by absolute error",
            "Forecast methodology gaps identified for process improvement",
            "Deviations classified as timing, methodology, or true surprises",
        ],
        current_state=[
            f"Actual-to-forecast comparison for {result.entity} {result.period}",
            f"{len(result.drivers)} accounts with measurable forecast deviation",
        ],
        constraints=[
            "Do not attribute forecast errors without methodology or timing context",
            "Rank by absolute forecast error, not directional spin",
        ],
        unknowns=[
            "Forecast methodology details behind each line item",
            "Whether deviations are systematic or account-specific",
        ],
        scope=["Forecast deviation ranking", "Accuracy narrative hardening"],
        origin_direction=["Prefer actionable forecast improvement over retrospective blame"],
        structural_vulnerabilities=[
            "Forecast deviations can be misattributed without methodology audit",
        ],
    )
    case = DecisionCase(
        decision_id=decision_id,
        title=f"Forecast variance review: {result.entity} {result.period}",
        domain="variance_copilot",
        created_at=datetime.now(timezone.utc).isoformat(),
        owner=owner, high_stakes=True,
        origin_system=origin_system, origin_model=origin_model,
        partner_system=partner_system, partner_model=partner_model,
        dossier=dossier,
    )
    disclosure = FoundationDisclosure(
        weakest_assumptions=[
            "Forecast column is internal management forecast (not budget or board guidance)",
            "Account-level aggregation is right for measuring forecast precision",
            "Forecast methodology is consistent across accounts being compared",
        ],
        invalidation_conditions=["Forecast vs budget confusion in the source data"],
        key_vulnerability="Forecast accuracy can look worse than reality if methodology differences aren't normalized.",
    )
    score = 78
    attack = FoundationAttack(
        assumption_attacks=[
            "Forecast may be based on different methodology for different departments.",
            "Aggregation may hide offsetting errors within an account.",
            "One-off events can distort accuracy without being a methodology failure.",
        ],
        invalidation_exploitation=["A large one-off item can make overall accuracy look systemic"],
        vulnerability_strike="Forecast process improvement requires understanding whether errors are random or systematic.",
        foundation_score=score,
        attack_summary="Forecast variance provides clear improvement signal, but root cause analysis requires methodology context.",
    )
    dossier.foundation_score = score
    dossier.prior_round_summary = [f"Top forecast deviations: {', '.join(top_driver_names)}"] if top_driver_names else []
    return case, disclosure, attack


def render_forecast_variance_markdown(result: ForecastVarianceResult) -> str:
    lines = [
        f"# Actual vs Forecast Variance Analysis",
        f"**Entity:** {result.entity}",
        f"**Period:** {result.period}",
        "",
        "## Forecast Accuracy",
        result.forecast_accuracy_summary,
        "",
        "## KPI Comparison",
    ]
    for kpi in result.kpis:
        lines.append(
            f"- {kpi.label}: actual={_fmt_currency(kpi.actual)} forecast={_fmt_currency(kpi.budget)} "
            f"var={_fmt_currency(kpi.variance)} ({kpi.variance_pct:.1%})"
        )
    lines.append("")
    lines.append("## Top Forecast Deviations")
    for idx, d in enumerate(result.drivers, start=1):
        lines.append(
            f"{idx}. {d.driver_name} | actual={_fmt_currency(d.actual)} | "
            f"forecast={_fmt_currency(d.budget)} | var={_fmt_currency(d.variance)} ({d.variance_pct:.1%})"
        )
        lines.append(f"   Insight: {d.insight}")
        lines.append(f"   Recommendation: {d.recommendation}")
    if result.other_bucket:
        lines.append(f"\nOther bucket: {_fmt_currency(result.other_bucket.variance)} across {result.other_bucket.count} items")
    if result.exec_summary_bullets:
        lines.extend(["", "## Executive Summary"] + [f"- {b}" for b in result.exec_summary_bullets])
    if result.risks: lines.extend(["", "## Risks"] + [f"- {r.text} [{r.severity}]" for r in result.risks])
    if result.opportunities: lines.extend(["", "## Opportunities"] + [f"- {o.text} [{o.size_hint}]" for o in result.opportunities])
    if result.suggested_actions: lines.extend(["", "## Suggested Actions"] + [f"- {a.text} | owner={a.owner_hint}" for a in result.suggested_actions])
    if result.audit_trail: lines.extend(["", "## Audit Trail"] + [
        f"- {a.statement}" for a in result.audit_trail
    ])
    return "\n".join(lines)


def render_forecast_variance_html(result: ForecastVarianceResult, *, session_summary: str = "") -> str:
    kpi_cards = "\n".join(
        f"""<div class="card kpi"><div class="label">{_escape_html(k.label)}</div>
          <div class="value">{_fmt_currency(k.variance)}</div>
          <div class="sub">Act {_fmt_currency(k.actual)} | Fcst {_fmt_currency(k.budget)}</div>
          <div class="variance {'neg' if k.variance < 0 else 'pos'}">{k.variance_pct:.1%}</div></div>"""
        for k in result.kpis
    )
    visible_rows = "\n".join(
        f"""<tr><td>{_escape_html(d.driver_name)}</td><td>{_escape_html(d.category)}</td>
          <td>{_fmt_currency(d.actual)}</td><td>{_fmt_currency(d.budget)}</td>
          <td class="{'neg' if d.variance < 0 else 'pos'}">{_fmt_currency(d.variance)}</td>
          <td>{d.variance_pct:.1%}</td></tr>"""
        for d in result.visible_drivers
    )
    driver_blocks = "\n".join(
        f"""<div class="card driver"><h3>{_escape_html(d.driver_name)}</h3>
          <p class="metric {'neg' if d.variance < 0 else 'pos'}">{_fmt_currency(d.variance)} ({d.variance_pct:.1%})</p>
          <p>{_escape_html(d.insight)}</p><p><strong>Rec:</strong> {_escape_html(d.recommendation)}</p></div>"""
        for d in result.drivers[:3]
    )
    exec_bullets = "".join(f"<li>{_escape_html(b)}</li>" for b in result.exec_summary_bullets)
    risks = "".join(f"<li><strong>{_escape_html(r.severity)}:</strong> {_escape_html(r.text)}</li>" for r in result.risks)
    def _pill(v: str | None) -> str:
        return f' <span class="pill">{_escape_html(v)}</span>' if v else ''
    opportunities = "".join(f"<li>{_escape_html(o.text)}{_pill(o.size_hint)}</li>" for o in result.opportunities)
    actions = "".join(f"<li>{_escape_html(a.text)} <span class=\"meta\">owner={_escape_html(a.owner_hint)}</span></li>" for a in result.suggested_actions)
    audit_items = "".join(f"<li>{_escape_html(a.statement)}</li>" for a in result.audit_trail)
    session_block = f"<section class='section'><h2>CHP Session</h2><pre>{_escape_html(session_summary)}</pre></section>" if session_summary else ""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Forecast Variance Studio</title><style>
:root {{ --bg:#f5f1e8; --panel:#fffdf8; --ink:#1f2520; --muted:#657166; --line:#d8cfbf; --accent:#134e4a; --good:#166534; --bad:#b91c1c; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:"Avenir Next","Segoe UI",sans-serif; background:linear-gradient(180deg,#f1eadb,#f7f4ed); color:var(--ink); }}
.wrap {{ max-width:1200px; margin:0 auto; padding:32px 24px 56px; }}
.hero,.summary-grid,.drivers-grid {{ display:grid; gap:20px; }}
.hero {{ grid-template-columns:2fr 1fr; align-items:start; margin-bottom:24px; }}
.summary-grid {{ grid-template-columns:repeat(3,1fr); }}
.drivers-grid {{ grid-template-columns:repeat(3,1fr); }}
.hero-card,.card,.section {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; box-shadow:0 12px 32px rgba(31,37,32,0.06); }}
.hero-card {{ padding:24px; }}
.section {{ padding:20px; margin-top:18px; }}
h1,h2,h3,p {{ margin:0; }}
h1 {{ font-size:2.2rem; letter-spacing:-0.03em; margin-bottom:8px; }}
.eyebrow {{ color:var(--accent); font-weight:700; text-transform:uppercase; letter-spacing:0.12em; font-size:0.75rem; margin-bottom:12px; }}
.subtext {{ color:var(--muted); margin-top:10px; line-height:1.5; }}
.value {{ font-size:1.9rem; font-weight:700; margin-top:8px; }}
.sub,.meta {{ color:var(--muted); font-size:0.9rem; margin-top:6px; }}
.variance,.metric {{ margin-top:12px; font-weight:700; }}
.pos {{ color:var(--good); }} .neg {{ color:var(--bad); }}
.driver {{ padding:18px; }} .driver p {{ margin-top:10px; line-height:1.45; }}
table {{ width:100%; border-collapse:collapse; margin-top:12px; font-size:0.95rem; }}
th,td {{ padding:12px 10px; border-bottom:1px solid var(--line); text-align:left; }}
th {{ color:var(--muted); font-size:0.78rem; text-transform:uppercase; letter-spacing:0.08em; }}
ul {{ margin:12px 0 0; padding-left:18px; line-height:1.55; }}
.pill {{ display:inline-block; margin-left:8px; padding:2px 8px; border-radius:999px; background:#e9efe7; color:var(--accent); font-size:0.8rem; }}
pre {{ white-space:pre-wrap; background:#f7f3ea; border-radius:12px; padding:14px; margin-top:10px; border:1px solid var(--line); font-size:0.85rem; line-height:1.5; }}
@media (max-width:900px) {{ .hero,.summary-grid,.drivers-grid {{ grid-template-columns:1fr; }} }}
</style></head><body><div class="wrap">
<section class="hero"><div class="hero-card"><div class="eyebrow">Forecast Variance Studio</div>
<h1>{_escape_html(result.entity)} — {_escape_html(result.period)}</h1>
<p class="subtext">{_escape_html(result.forecast_accuracy_summary)}</p></div>
<div class="hero-card"><div class="eyebrow">Forecast Accuracy</div>
<p>{result.shown_driver_count} deviation drivers visible</p></div></section>
<section class="section"><h2>KPI: Actual vs Forecast</h2><div class="summary-grid">{kpi_cards}</div></section>
<section class="section"><h2>Deviations</h2><table><thead><tr><th>Driver</th><th>Cat</th><th>Actual</th><th>Forecast</th><th>Var</th><th>Var%</th></tr></thead><tbody>{visible_rows}</tbody></table></section>
<section class="section"><h2>Top Deviations</h2><div class="drivers-grid">{driver_blocks}</div></section>
<section class="section"><h2>Executive Summary</h2><ul>{exec_bullets}</ul></section>
<section class="section"><h2>Risks</h2><ul>{risks}</ul></section>
<section class="section"><h2>Opportunities</h2><ul>{opportunities}</ul></section>
<section class="section"><h2>Suggested Actions</h2><ul>{actions}</ul></section>
<section class="section"><h2>Audit Trail</h2><ul>{audit_items}</ul></section>
{session_block}
</div></body></html>"""
