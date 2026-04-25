"""CFO decision impact simulator."""
from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from cme.chp.models import DecisionCase, Dossier, FoundationAttack, FoundationDisclosure


HIRING_PLAN_OPTIONS = {
    "freeze": {"monthly_hires": 0, "label": "Freeze"},
    "moderate": {"monthly_hires": 1, "label": "Moderate growth"},
    "aggressive": {"monthly_hires": 3, "label": "Aggressive growth"},
}


@dataclass
class SimulatorInputs:
    cash_balance: float = 1_200_000.0
    monthly_revenue: float = 420_000.0
    gross_margin_pct: float = 0.72
    monthly_operating_expenses: float = 360_000.0
    headcount: int = 28
    monthly_churn_pct: float = 0.018
    new_customers_per_month: int = 10
    average_contract_value: float = 9_500.0
    ar_days: float = 42.0
    ap_days: float = 28.0
    pricing_change_pct: float = 0.0
    new_customer_growth_change_pct: float = 0.0
    churn_improvement_pct: float = 0.0
    expansion_revenue_pct: float = 0.02
    hiring_plan: str = "moderate"
    salary_cost_change_pct: float = 0.0
    non_payroll_cost_change_pct: float = 0.0
    ar_days_change: float = 0.0
    ap_days_change: float = 0.0
    demand_shock_pct: float = 0.0
    cost_shock_pct: float = 0.0
    horizon_months: int = 24


@dataclass
class SimulatorMonth:
    month_index: int
    label: str
    revenue: float
    gross_profit: float
    operating_expenses: float
    ebitda: float
    burn: float
    cash_balance: float
    headcount: int
    working_capital_impact: float
    new_customers: float
    churn_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SimulatorResult:
    inputs: SimulatorInputs
    months: List[SimulatorMonth]
    runway_months: float
    resilience_score: int
    growth_health_score: int
    commentary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inputs": asdict(self.inputs),
            "months": [row.to_dict() for row in self.months],
            "runway_months": self.runway_months,
            "resilience_score": self.resilience_score,
            "growth_health_score": self.growth_health_score,
            "commentary": self.commentary,
        }


def build_decision_impact_simulation(inputs: SimulatorInputs) -> SimulatorResult:
    hiring = HIRING_PLAN_OPTIONS.get(inputs.hiring_plan, HIRING_PLAN_OPTIONS["moderate"])
    months: List[SimulatorMonth] = []
    cash = inputs.cash_balance
    revenue = inputs.monthly_revenue
    headcount = inputs.headcount
    current_customers = max(1.0, inputs.monthly_revenue / max(1.0, inputs.average_contract_value))
    salary_base = inputs.monthly_operating_expenses * 0.72
    non_payroll_base = inputs.monthly_operating_expenses - salary_base

    for idx in range(1, inputs.horizon_months + 1):
        pricing_factor = 1 + inputs.pricing_change_pct
        demand_factor = 1 + inputs.demand_shock_pct
        customer_growth_factor = 1 + inputs.new_customer_growth_change_pct
        churn_factor = max(0.1, 1 - inputs.churn_improvement_pct)
        expansion_factor = 1 + inputs.expansion_revenue_pct
        effective_new_customers = inputs.new_customers_per_month * customer_growth_factor * demand_factor
        effective_churn = max(0.0, inputs.monthly_churn_pct * churn_factor)

        churned_customers = current_customers * effective_churn
        current_customers = max(1.0, current_customers + effective_new_customers - churned_customers)

        average_contract_value = inputs.average_contract_value * pricing_factor * expansion_factor
        revenue = current_customers * average_contract_value
        gross_margin = max(0.15, min(0.95, inputs.gross_margin_pct - inputs.cost_shock_pct))
        gross_profit = revenue * gross_margin

        headcount += hiring["monthly_hires"]
        salary_cost = salary_base * (headcount / max(1, inputs.headcount)) * (1 + inputs.salary_cost_change_pct)
        non_payroll = non_payroll_base * (1 + inputs.non_payroll_cost_change_pct)
        operating_expenses = salary_cost + non_payroll

        ar_effect = revenue * (inputs.ar_days_change / 30.0) * -1
        ap_effect = (revenue * (1 - gross_margin)) * (inputs.ap_days_change / 30.0)
        working_capital_impact = ar_effect + ap_effect

        ebitda = gross_profit - operating_expenses
        cash += ebitda + working_capital_impact
        burn = max(0.0, -ebitda)

        months.append(
            SimulatorMonth(
                month_index=idx,
                label=f"M{idx:02d}",
                revenue=round(revenue, 2),
                gross_profit=round(gross_profit, 2),
                operating_expenses=round(operating_expenses, 2),
                ebitda=round(ebitda, 2),
                burn=round(burn, 2),
                cash_balance=round(cash, 2),
                headcount=headcount,
                working_capital_impact=round(working_capital_impact, 2),
                new_customers=round(effective_new_customers, 2),
                churn_pct=round(effective_churn, 4),
            )
        )

    runway = _runway_months(months, inputs.cash_balance)
    resilience = _resilience_score(months, runway)
    growth_health = _growth_health_score(months)
    commentary = _commentary(months, runway, resilience, growth_health)
    return SimulatorResult(
        inputs=inputs,
        months=months,
        runway_months=round(runway, 1),
        resilience_score=resilience,
        growth_health_score=growth_health,
        commentary=commentary,
    )


def build_decision_impact_case(
    result: SimulatorResult,
    *,
    owner: str = "cfo",
    origin_system: str = "Claude",
    origin_model: str = "GPT-5.4",
    partner_system: str = "Partner",
    partner_model: str = "GPT-5-equivalent",
) -> tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    min_cash = min(row.cash_balance for row in result.months)
    min_ebitda = min(row.ebitda for row in result.months)
    dossier = Dossier(
        core_problem="Evaluate how a small set of CFO decisions changes cash, runway, growth, and profitability over the next 12-24 months.",
        goal_state=[
            "Cause and effect between operating levers and financial outcomes is visible immediately",
            "Liquidity, growth, and profitability tradeoffs are explicit",
            "Management can compare resilience versus growth posture without rebuilding a model",
        ],
        current_state=[
            f"Opening cash is ${result.inputs.cash_balance:,.0f}",
            f"Lowest projected cash is ${min_cash:,.0f}",
            f"Lowest EBITDA is ${min_ebitda:,.0f}",
            f"Resilience score is {result.resilience_score}/100",
        ],
        prior_decisions=[],
        constraints=[
            "Model uses a compact input set suitable for rapid CFO review",
            "Working capital impact is simplified to AR/AP timing effects",
            "Hiring plan is scenario-based rather than org-chart detailed",
        ],
        unknowns=[
            "Real-world conversion and retention may shift outside the simplified driver set",
            "Some non-cash items are excluded for speed and clarity",
        ],
        scope=[
            "Revenue and customer drivers",
            "Cost and hiring posture",
            "Working capital timing",
            "Risk and resilience scoring",
        ],
        origin_direction=[
            "Make tradeoffs visible faster than a traditional board model",
            "Prefer transparent simplification over opaque precision",
        ],
        structural_vulnerabilities=[
            "A compact simulator can understate second-order effects that appear in a full model",
            "Working capital simplification can make cash timing look smoother than reality",
        ],
    )
    case = DecisionCase(
        decision_id=f"decision-sim-{result.inputs.horizon_months}m",
        title="CFO decision impact simulator",
        domain="decision_impact_simulator",
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
            "A short driver list is enough to approximate the key finance tradeoffs",
            "Runway and resilience can be represented meaningfully without full accounting detail",
            "Users will understand the simulator as directional rather than deterministic",
        ],
        invalidation_conditions=[
            "Important second-order effects dominate the outcome more than the modeled levers do",
            "A user treats the simulator as a full forecast instead of a decision cockpit",
        ],
        key_vulnerability="The simulator is most exposed where simplified levers are mistaken for complete operating reality.",
    )
    score = 84
    if min_cash < 0:
        score -= 10
    if result.resilience_score < 40:
        score -= 8
    attack = FoundationAttack(
        assumption_attacks=[
            "The compact input set may hide important interactions between growth, gross margin, and execution capacity.",
            "Working capital timing can look more controllable in a cockpit than it is in operations.",
            "A score can imply precision even when the underlying mechanics are intentionally simplified.",
        ],
        invalidation_exploitation=[
            "One unmodeled shock can overwhelm the apparent gains from pricing, hiring, or collection changes.",
            "If the user reads the simulator as a formal forecast, decision confidence will be overstated.",
        ],
        vulnerability_strike="The tool works only if users treat it as a fast directional cockpit rather than a substitute for the full planning model.",
        foundation_score=max(60, min(92, score)),
        attack_summary="The simulator is valuable for rapid decision framing, but it needs clear guardrails so speed does not get confused with precision.",
    )
    dossier.foundation_score = attack.foundation_score
    dossier.prior_round_summary = [f"Resilience score: {result.resilience_score}"]
    return case, disclosure, attack


def render_decision_impact_markdown(result: SimulatorResult) -> str:
    lines = [
        "# CFO Decision Impact Simulator",
        f"**Runway:** {result.runway_months:.1f} months",
        f"**Resilience Score:** {result.resilience_score}/100",
        f"**Growth Health:** {result.growth_health_score}/100",
        "",
        result.commentary,
        "",
        "## First 6 Months",
    ]
    for row in result.months[:6]:
        lines.append(
            f"- {row.label} | revenue=${row.revenue:,.0f} | ebitda=${row.ebitda:,.0f} | "
            f"cash=${row.cash_balance:,.0f} | headcount={row.headcount}"
        )
    return "\n".join(lines)


def render_decision_impact_html(result: SimulatorResult, *, session_summary: str = "") -> str:
    def metric_card(label: str, value: str, hint: str, tone: str = "") -> str:
        return (
            f"<div class='kpi {tone}'><div class='label'>{_escape(label)}</div>"
            f"<div class='value'>{_escape(value)}</div><div class='sub'>{_escape(hint)}</div></div>"
        )

    chart_blocks = "".join(
        [
            _spark_block("Projected Cash", [row.cash_balance for row in result.months], "#153b5c", _fmt_money(result.months[-1].cash_balance)),
            _spark_block("Projected Revenue", [row.revenue for row in result.months], "#c86a3b", _fmt_money(result.months[-1].revenue)),
            _spark_block("EBITDA / Burn", [row.ebitda for row in result.months], "#1f7a45", _fmt_money(result.months[-1].ebitda)),
            _spark_block("Headcount Trend", [float(row.headcount) for row in result.months], "#6d4c9f", str(result.months[-1].headcount)),
            _spark_block("Working Capital Impact", [row.working_capital_impact for row in result.months], "#aa3030", _fmt_money(sum(row.working_capital_impact for row in result.months))),
        ]
    )
    session_block = (
        f"<section class='section'><h2>CHP Session</h2><pre>{_escape(session_summary)}</pre></section>"
        if session_summary
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CFO Decision Impact Simulator</title>
  <style>
    :root {{
      --bg: #f4efe7;
      --panel: #fffdf8;
      --ink: #132238;
      --muted: #5c675d;
      --line: #d8cfbf;
      --accent: #153b5c;
      --accent2: #c86a3b;
      --good: #1f7a45;
      --warn: #b7791f;
      --bad: #aa3030;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(200, 106, 59, 0.18), transparent 26%),
        linear-gradient(180deg, #efe6d6 0%, #f7f4ed 100%);
    }}
    .wrap {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px 24px 56px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 18px;
      margin-bottom: 20px;
    }}
    .panel, .section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: 0 14px 32px rgba(19, 34, 56, 0.07);
    }}
    .panel {{ padding: 24px; }}
    .section {{ padding: 20px; margin-top: 18px; }}
    .eyebrow {{
      color: var(--accent2);
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{ font-size: 2.25rem; letter-spacing: -0.03em; margin-top: 8px; }}
    .subtext {{ color: var(--muted); margin-top: 10px; line-height: 1.5; }}
    .layout {{
      display: grid;
      grid-template-columns: 0.9fr 1.1fr;
      gap: 20px;
      align-items: start;
    }}
    .input-grid, .kpi-grid, .chart-grid {{
      display: grid;
      gap: 14px;
    }}
    .input-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .kpi-grid {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
    .chart-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .card {{
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #fffaf2;
    }}
    .label {{ color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    .value {{ font-size: 1.8rem; font-weight: 700; margin-top: 8px; }}
    .sub {{ color: var(--muted); margin-top: 6px; line-height: 1.4; }}
    .kpi.good .value {{ color: var(--good); }}
    .kpi.warn .value {{ color: var(--warn); }}
    .kpi.bad .value {{ color: var(--bad); }}
    .cluster-title {{ font-size: 1rem; font-weight: 700; margin-bottom: 10px; }}
    .scorebar {{
      height: 14px;
      border-radius: 999px;
      background: linear-gradient(90deg, #be3434 0%, #d9a441 55%, #207a45 100%);
      position: relative;
      margin-top: 10px;
      overflow: hidden;
    }}
    .scorebar::after {{
      content: "";
      position: absolute;
      top: 0;
      bottom: 0;
      left: {result.resilience_score}%;
      width: 4px;
      background: #132238;
    }}
    .score-meta {{ margin-top: 8px; color: var(--muted); font-size: 0.9rem; }}
    .spark {{
      padding: 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #fffdf8 0%, #faf5eb 100%);
    }}
    .spark-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 8px;
    }}
    .spark-value {{ font-weight: 700; color: var(--accent); }}
    svg {{ width: 100%; height: 180px; }}
    .commentary {{
      line-height: 1.6;
      font-size: 1rem;
    }}
    .mini-list {{
      margin: 12px 0 0;
      padding-left: 18px;
      line-height: 1.55;
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
    @media (max-width: 980px) {{
      .hero, .layout, .kpi-grid, .chart-grid, .input-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="panel">
        <div class="eyebrow">CFO Decision Impact Simulator</div>
        <h1>Fast cause-and-effect for growth, cash, and resilience</h1>
        <p class="subtext">A lightweight financial cockpit for testing pricing, hiring, churn, working capital, and shock scenarios over the next {result.inputs.horizon_months} months.</p>
      </div>
      <div class="panel">
        <div class="eyebrow">Resilience Score</div>
        <div class="value">{result.resilience_score}/100</div>
        <div class="scorebar"></div>
        <div class="score-meta">Growth health {result.growth_health_score}/100 | runway {result.runway_months:.1f} months</div>
      </div>
    </section>
    <section class="layout">
      <div class="panel">
        <div class="cluster-title">Starting Point</div>
        <div class="input-grid">
          {metric_card("Cash balance", _fmt_money(result.inputs.cash_balance), "Current liquidity")}
          {metric_card("Monthly revenue", _fmt_money(result.inputs.monthly_revenue), "Starting topline")}
          {metric_card("Gross margin", f"{result.inputs.gross_margin_pct:.1%}", "Initial margin profile")}
          {metric_card("Monthly opex", _fmt_money(result.inputs.monthly_operating_expenses), "Operating cost base")}
          {metric_card("Headcount", str(result.inputs.headcount), "Current team size")}
          {metric_card("Monthly churn", f"{result.inputs.monthly_churn_pct:.1%}", "Starting customer attrition")}
        </div>
        <div class="cluster-title" style="margin-top: 18px;">Growth Drivers</div>
        <ul class="mini-list">
          <li>Pricing change: {_fmt_pct(result.inputs.pricing_change_pct)}</li>
          <li>New-customer growth change: {_fmt_pct(result.inputs.new_customer_growth_change_pct)}</li>
          <li>Churn improvement: {_fmt_pct(result.inputs.churn_improvement_pct)}</li>
          <li>Expansion revenue: {_fmt_pct(result.inputs.expansion_revenue_pct)}</li>
          <li>Hiring plan: {_escape(result.inputs.hiring_plan)}</li>
          <li>Salary cost change: {_fmt_pct(result.inputs.salary_cost_change_pct)}</li>
          <li>Non-payroll cost change: {_fmt_pct(result.inputs.non_payroll_cost_change_pct)}</li>
          <li>AR days change: {result.inputs.ar_days_change:+.0f} days</li>
          <li>AP days change: {result.inputs.ap_days_change:+.0f} days</li>
          <li>Demand shock: {_fmt_pct(result.inputs.demand_shock_pct)}</li>
          <li>Cost shock: {_fmt_pct(result.inputs.cost_shock_pct)}</li>
        </ul>
      </div>
      <div>
        <section class="section">
          <div class="kpi-grid">
            {metric_card("Cash runway", f"{result.runway_months:.1f} months", "Large-card runway view", _tone(result.runway_months, result.months[-1].ebitda))}
            {metric_card("Monthly burn", _fmt_money(max(row.burn for row in result.months)), "Peak burn under this scenario", _tone(result.runway_months, -1))}
            {metric_card("Revenue growth", f"{_growth_rate(result.months):.1f}%", "Month 1 to month 24", "good")}
            {metric_card("Operating margin", f"{_operating_margin(result.months[-1]):.1f}%", "End-of-horizon EBITDA margin", _tone(result.runway_months, result.months[-1].ebitda))}
          </div>
        </section>
        <section class="section">
          <div class="chart-grid">
            {chart_blocks}
          </div>
        </section>
        <section class="section">
          <h2>AI Commentary</h2>
          <p class="commentary">{_escape(result.commentary)}</p>
        </section>
        {session_block}
      </div>
    </section>
  </div>
</body>
</html>
"""


def _runway_months(months: List[SimulatorMonth], opening_cash: float) -> float:
    negative = next((row for row in months if row.cash_balance < 0), None)
    if negative:
        return max(0.0, float(negative.month_index - 1))
    burn_rows = [row for row in months[:6] if row.ebitda < 0]
    if not burn_rows:
        return 99.0
    avg_burn = abs(sum(row.ebitda for row in burn_rows) / len(burn_rows))
    if avg_burn == 0:
        return 99.0
    return opening_cash / avg_burn


def _resilience_score(months: List[SimulatorMonth], runway: float) -> int:
    last = months[-1]
    min_cash = min(row.cash_balance for row in months)
    score = 35
    score += min(30, max(0, runway) * 2.0)
    score += 15 if min_cash > 0 else 0
    score += min(20, max(-10.0, _operating_margin(last)) + 10)
    return max(0, min(100, int(round(score))))


def _growth_health_score(months: List[SimulatorMonth]) -> int:
    growth = _growth_rate(months)
    churn = months[-1].churn_pct * 100
    score = 50 + growth * 0.4 - churn * 4
    return max(0, min(100, int(round(score))))


def _growth_rate(months: List[SimulatorMonth]) -> float:
    start = months[0].revenue
    end = months[-1].revenue
    if start == 0:
        return 0.0
    return ((end - start) / start) * 100.0


def _operating_margin(month: SimulatorMonth) -> float:
    if month.revenue == 0:
        return 0.0
    return (month.ebitda / month.revenue) * 100.0


def _commentary(
    months: List[SimulatorMonth],
    runway: float,
    resilience_score: int,
    growth_health_score: int,
) -> str:
    first = months[0]
    last = months[-1]
    runway_text = (
        f"Runway compresses to about {runway:.1f} months"
        if runway < 24
        else f"Runway stays comfortable at roughly {runway:.1f} months"
    )
    growth_text = (
        f"revenue grows from {_fmt_money(first.revenue)} to {_fmt_money(last.revenue)}"
        if last.revenue >= first.revenue
        else f"revenue declines from {_fmt_money(first.revenue)} to {_fmt_money(last.revenue)}"
    )
    margin_text = (
        "profitability improves meaningfully"
        if last.ebitda > first.ebitda
        else "profitability weakens under the current settings"
    )
    suggestion = (
        "This balances growth and resilience well."
        if resilience_score >= 65 and growth_health_score >= 60
        else "You have improved one dimension, but the tradeoff needs careful review."
    )
    return f"{runway_text} while {growth_text} and {margin_text}. {suggestion}"


def _spark_block(title: str, series: str, kind: str) -> str:
    raise NotImplementedError


def _spark_block(title: str, series: List[float], color: str, summary: str) -> str:
    return (
        f"<div class='spark'>"
        f"<div class='spark-head'><div class='label'>{_escape(title)}</div><div class='spark-value'>{_escape(summary)}</div></div>"
        f"{_spark_svg(series, color)}"
        f"</div>"
    )


def _spark_svg(series: List[float], color: str) -> str:
    if not series:
        return "<svg viewBox='0 0 520 180'></svg>"
    width = 520.0
    height = 180.0
    left = 14.0
    top = 12.0
    bottom = 160.0
    right = 500.0
    min_value = min(series)
    max_value = max(series)
    spread = max(max_value - min_value, 1.0)

    points: List[str] = []
    for idx, value in enumerate(series):
        x = left + (right - left) * (idx / max(1, len(series) - 1))
        y = bottom - ((value - min_value) / spread) * (bottom - top)
        points.append(f"{x:.1f},{y:.1f}")
    line = " ".join(points)
    area = f"{left:.1f},{bottom:.1f} " + line + f" {right:.1f},{bottom:.1f}"
    midline = top + (bottom - top) / 2
    return (
        "<svg viewBox='0 0 520 180' role='img' aria-hidden='true'>"
        f"<line x1='{left:.1f}' y1='{midline:.1f}' x2='{right:.1f}' y2='{midline:.1f}' stroke='#ddd3c5' stroke-width='1' stroke-dasharray='4 6' />"
        f"<polygon points='{area}' fill='{color}22' />"
        f"<polyline points='{line}' fill='none' stroke='{color}' stroke-width='4' stroke-linecap='round' stroke-linejoin='round' />"
        f"<circle cx='{points[-1].split(',')[0]}' cy='{points[-1].split(',')[1]}' r='4.5' fill='{color}' />"
        "</svg>"
    )


def _fmt_money(value: float) -> str:
    return f"${value:,.0f}"


def _fmt_pct(value: float) -> str:
    return f"{value:+.1%}"


def _tone(runway: float, ebitda: float) -> str:
    if runway < 9 or ebitda < 0:
        return "warn" if runway >= 6 else "bad"
    return "good"


def _escape(value: str | float) -> str:
    return html.escape(str(value), quote=True)
