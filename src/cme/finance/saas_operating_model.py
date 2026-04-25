"""24-month SaaS operating model with driver-based forecasting."""
from __future__ import annotations

import csv
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


SEASON_LENGTH = 12


@dataclass
class MRRHistoryRow:
    month: str
    customers_start: int
    new_customers: int
    churned_customers: int
    customers_end: int
    churn_pct: float
    arpa: float
    mrr_actual: float


@dataclass
class OperatingModelAssumptions:
    company_name: str
    opening_cash_usd: float
    current_customers: int
    current_arpa: float
    gross_margin_pct: float
    monthly_opex_usd: float
    current_headcount: int
    horizon_months: int = 24
    default_churn_pct: float = 0.02
    starting_new_customers: int = 10
    new_customers_increment_per_month: int = 1
    arpa_step_up_usd: float = 50.0
    arpa_step_up_every_months: int = 6
    hires_per_wave: int = 5
    hire_every_months: int = 4
    recruitment_cost_per_wave_usd: float = 30_000.0
    annual_salary_increase_pct: float = 0.10
    fundraise_month_number: int = 12
    fundraise_amount_usd: float = 1_000_000.0


@dataclass
class DriverForecastPoint:
    month_index: int
    label: str
    new_customers: float
    churn_pct: float
    arpa: float
    hires: int
    fundraise_usd: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OperatingModelMonth:
    month_index: int
    label: str
    customers_start: int
    new_customers: int
    churned_customers: int
    customers_end: int
    churn_pct: float
    arpa: float
    mrr: float
    revenue: float
    gross_profit: float
    headcount: int
    hires: int
    opex: float
    ebitda: float
    fundraise_usd: float
    opening_cash: float
    closing_cash: float
    runway_months: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SaaSOperatingModelResult:
    assumptions: OperatingModelAssumptions
    driver_forecast: List[DriverForecastPoint] = field(default_factory=list)
    monthly_rows: List[OperatingModelMonth] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assumptions": asdict(self.assumptions),
            "driver_forecast": [row.to_dict() for row in self.driver_forecast],
            "monthly_rows": [row.to_dict() for row in self.monthly_rows],
            "key_findings": self.key_findings,
        }


def load_mrr_history_csv(path: str | Path) -> List[MRRHistoryRow]:
    rows: List[MRRHistoryRow] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            rows.append(
                MRRHistoryRow(
                    month=raw["Month"].strip(),
                    customers_start=int(_to_float(raw["Customers Start"])),
                    new_customers=int(_to_float(raw["New customers"])),
                    churned_customers=int(_to_float(raw["Churned Customers"])),
                    customers_end=int(_to_float(raw["Customers End"])),
                    churn_pct=_parse_pct(raw["Churn %"]),
                    arpa=_to_float(raw["ARPA"]),
                    mrr_actual=_to_float(raw["MRR_Actual"]),
                )
            )
    return rows


def build_24_month_saas_operating_model(
    assumptions: OperatingModelAssumptions,
    *,
    history_rows: Iterable[MRRHistoryRow] | None = None,
) -> SaaSOperatingModelResult:
    history_rows = list(history_rows or [])
    driver_forecast = _build_driver_forecast(assumptions, history_rows)
    monthly_rows = _build_monthly_rows(assumptions, driver_forecast)
    return SaaSOperatingModelResult(
        assumptions=assumptions,
        driver_forecast=driver_forecast,
        monthly_rows=monthly_rows,
        key_findings=_build_key_findings(monthly_rows, assumptions),
    )


def build_saas_operating_model_case(
    result: SaaSOperatingModelResult,
    *,
    owner: str = "cfo",
    origin_system: str = "Claude",
    origin_model: str = "GPT-5.4",
    partner_system: str = "Partner",
    partner_model: str = "GPT-5-equivalent",
) -> tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    rows = result.monthly_rows
    min_cash = min(row.closing_cash for row in rows)
    min_runway = min(row.runway_months for row in rows)
    first_negative = next((row.label for row in rows if row.closing_cash < 0), "NONE")
    last_row = rows[-1]
    dossier = Dossier(
        core_problem=f"Stress-test the 24-month SaaS operating model for {result.assumptions.company_name} before it is used for planning or fundraising.",
        goal_state=[
            "Monthly customer, revenue, EBITDA, and cash outputs are internally consistent",
            "Runway pressure and financing dependencies are visible before board use",
            "Driver assumptions have explicit flip criteria",
        ],
        current_state=[
            f"Opening cash is ${result.assumptions.opening_cash_usd:,.0f}",
            f"Lowest projected cash is ${min_cash:,.0f}",
            f"Lowest projected runway is {min_runway:.1f} months",
            f"Month 24 closing cash is ${last_row.closing_cash:,.0f}",
        ],
        prior_decisions=[],
        constraints=[
            "Model uses simple cash accounting",
            "Headcount drives most opex growth",
            "Fundraise timing is explicit rather than implied",
        ],
        unknowns=[
            "Pipeline conversion may diverge from the customer-acquisition forecast",
            "Hiring pace may change if burn exceeds plan",
        ],
        scope=[
            "Driver forecast",
            "Operating plan",
            "Cash and runway review",
        ],
        origin_direction=[
            "Prefer conservative reading of runway around the fundraising window",
            "Treat hiring as a controlled lever, not a passive consequence of growth",
        ],
        structural_vulnerabilities=[
            "Driver forecasts can overstate topline durability if churn worsens after hiring ramps",
            "The financing plan can hide an execution shortfall until cash is already constrained",
        ],
    )
    case = DecisionCase(
        decision_id=f"saas-24m-{result.assumptions.company_name.lower().replace(' ', '-')}",
        title=f"24-month SaaS operating model for {result.assumptions.company_name}",
        domain="saas_operating_model",
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
            "Customer acquisition can hold its forecast path while churn remains controlled",
            "Headcount-driven opex scales in line with hiring assumptions",
            "The planned fundraise lands on time and at the modeled amount",
        ],
        invalidation_conditions=[
            "New-customer adds or churn diverge enough to break the MRR path",
            "The financing event slips while EBITDA remains negative",
        ],
        key_vulnerability="The model is most exposed where growth hiring and financing timing reinforce each other.",
    )
    score = 84
    if min_cash < 0:
        score -= 12
    if first_negative != "NONE":
        score -= 5
    if min_runway < 6:
        score -= 7
    attack = FoundationAttack(
        assumption_attacks=[
            "Acquisition forecasts may extrapolate momentum that the GTM engine cannot sustain for 24 months.",
            "Opex may rise faster than modeled if support and infrastructure lag revenue growth.",
            "Fundraise timing may be treated as certain even though the model still needs outside capital to stay comfortable.",
        ],
        invalidation_exploitation=[
            "A modest churn spike can compress MRR and push cash stress forward by several months.",
            "Any financing delay can expose how much of the plan depends on external capital rather than operating improvement.",
        ],
        vulnerability_strike="The model can look healthy while still being structurally dependent on near-perfect sequencing of growth, hiring, and financing.",
        foundation_score=max(58, min(91, score)),
        attack_summary="The plan is useful for scenario planning, but it should not be treated as a base case until driver sensitivity and financing dependence are explicitly challenged.",
    )
    dossier.foundation_score = attack.foundation_score
    dossier.prior_round_summary = [f"First negative cash month: {first_negative}"]
    return case, disclosure, attack


def render_saas_operating_model_markdown(result: SaaSOperatingModelResult) -> str:
    rows = result.monthly_rows
    lines = [
        "# 24-Month SaaS Operating Model",
        f"**Company:** {result.assumptions.company_name}",
        f"**Opening Cash:** ${result.assumptions.opening_cash_usd:,.0f}",
        "",
        "## Key Findings",
    ]
    for item in result.key_findings:
        lines.append(f"- {item}")
    lines.extend(["", "## First 6 Months"])
    for row in rows[:6]:
        lines.append(
            f"- {row.label} | customers={row.customers_end} | mrr=${row.mrr:,.0f} | "
            f"ebitda=${row.ebitda:,.0f} | close_cash=${row.closing_cash:,.0f} | runway={row.runway_months:.1f}"
        )
    lines.extend(["", "## Last 6 Months"])
    for row in rows[-6:]:
        lines.append(
            f"- {row.label} | customers={row.customers_end} | mrr=${row.mrr:,.0f} | "
            f"ebitda=${row.ebitda:,.0f} | close_cash=${row.closing_cash:,.0f} | runway={row.runway_months:.1f}"
        )
    return "\n".join(lines)


def export_saas_operating_model_workbook(
    result: SaaSOperatingModelResult,
    *,
    session_summary: str,
    output_path: str | Path,
) -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    builder_path = repo_root / "tools" / "build_saas_operating_model_workbook.mjs"
    node_path = _resolve_node_path()
    _ensure_node_modules_link(repo_root)
    payload = {
        "model": result.to_dict(),
        "session_summary": session_summary,
    }
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


def _build_driver_forecast(
    assumptions: OperatingModelAssumptions,
    history_rows: List[MRRHistoryRow],
) -> List[DriverForecastPoint]:
    if history_rows:
        new_series = [float(row.new_customers) for row in history_rows]
        churn_series = [float(row.churn_pct) for row in history_rows]
        new_forecast = _holt_winters_additive(new_series, assumptions.horizon_months, floor=0.0)
        churn_forecast = _holt_winters_additive(churn_series, assumptions.horizon_months, floor=0.002, ceiling=0.10)
    else:
        new_forecast = [
            float(assumptions.starting_new_customers + idx * assumptions.new_customers_increment_per_month)
            for idx in range(assumptions.horizon_months)
        ]
        churn_forecast = [assumptions.default_churn_pct for _ in range(assumptions.horizon_months)]

    forecast: List[DriverForecastPoint] = []
    for idx in range(assumptions.horizon_months):
        month_number = idx + 1
        arpa_steps = idx // assumptions.arpa_step_up_every_months
        arpa = assumptions.current_arpa + arpa_steps * assumptions.arpa_step_up_usd
        hires = assumptions.hires_per_wave if month_number % assumptions.hire_every_months == 0 else 0
        fundraise = assumptions.fundraise_amount_usd if month_number == assumptions.fundraise_month_number else 0.0
        forecast.append(
            DriverForecastPoint(
                month_index=month_number,
                label=f"M{month_number:02d}",
                new_customers=round(new_forecast[idx], 2),
                churn_pct=round(churn_forecast[idx], 4),
                arpa=round(arpa, 2),
                hires=hires,
                fundraise_usd=fundraise,
            )
        )
    return forecast


def _build_monthly_rows(
    assumptions: OperatingModelAssumptions,
    driver_forecast: List[DriverForecastPoint],
) -> List[OperatingModelMonth]:
    rows: List[OperatingModelMonth] = []
    opening_cash = assumptions.opening_cash_usd
    customers_start = assumptions.current_customers
    headcount = assumptions.current_headcount
    base_opex_per_employee = assumptions.monthly_opex_usd / max(1, assumptions.current_headcount)

    for idx, driver in enumerate(driver_forecast):
        annual_salary_multiplier = (1 + assumptions.annual_salary_increase_pct) ** (idx / 12)
        new_customers = max(0, int(round(driver.new_customers)))
        churned = max(0, int(round(customers_start * driver.churn_pct)))
        customers_end = max(0, customers_start + new_customers - churned)
        headcount += driver.hires
        salary_opex = headcount * base_opex_per_employee * annual_salary_multiplier
        recruitment_opex = assumptions.recruitment_cost_per_wave_usd if driver.hires else 0.0
        opex = salary_opex + recruitment_opex
        mrr = customers_end * driver.arpa
        revenue = mrr
        gross_profit = revenue * assumptions.gross_margin_pct
        ebitda = gross_profit - opex
        closing_cash = opening_cash + ebitda + driver.fundraise_usd
        runway_months = _runway_months(closing_cash, ebitda)
        rows.append(
            OperatingModelMonth(
                month_index=driver.month_index,
                label=driver.label,
                customers_start=customers_start,
                new_customers=new_customers,
                churned_customers=churned,
                customers_end=customers_end,
                churn_pct=driver.churn_pct,
                arpa=driver.arpa,
                mrr=round(mrr, 2),
                revenue=round(revenue, 2),
                gross_profit=round(gross_profit, 2),
                headcount=headcount,
                hires=driver.hires,
                opex=round(opex, 2),
                ebitda=round(ebitda, 2),
                fundraise_usd=driver.fundraise_usd,
                opening_cash=round(opening_cash, 2),
                closing_cash=round(closing_cash, 2),
                runway_months=round(runway_months, 2),
            )
        )
        opening_cash = closing_cash
        customers_start = customers_end
    return rows


def _build_key_findings(rows: List[OperatingModelMonth], assumptions: OperatingModelAssumptions) -> List[str]:
    min_cash_row = min(rows, key=lambda row: row.closing_cash)
    max_mrr_row = max(rows, key=lambda row: row.mrr)
    negative_row = next((row for row in rows if row.closing_cash < 0), None)
    findings = [
        f"MRR grows to ${max_mrr_row.mrr:,.0f} by {max_mrr_row.label}.",
        f"Lowest cash balance is ${min_cash_row.closing_cash:,.0f} in {min_cash_row.label}.",
        f"Headcount reaches {rows[-1].headcount} by month {assumptions.horizon_months}.",
    ]
    if negative_row:
        findings.append(f"Cash turns negative in {negative_row.label} without a plan change.")
    else:
        findings.append("Cash remains positive through the forecast horizon under the current assumptions.")
    return findings


def _holt_winters_additive(
    series: List[float],
    horizon: int,
    *,
    floor: float | None = None,
    ceiling: float | None = None,
) -> List[float]:
    if len(series) < SEASON_LENGTH * 2:
        return _simple_growth_forecast(series, horizon, floor=floor, ceiling=ceiling)

    alpha = 0.45
    beta = 0.20
    gamma = 0.25
    seasonals = _initial_seasonals(series)
    level = sum(series[:SEASON_LENGTH]) / SEASON_LENGTH
    trend = (
        sum(series[SEASON_LENGTH : SEASON_LENGTH * 2]) - sum(series[:SEASON_LENGTH])
    ) / (SEASON_LENGTH * SEASON_LENGTH)

    for idx, actual in enumerate(series):
        seasonal = seasonals[idx % SEASON_LENGTH]
        prev_level = level
        level = alpha * (actual - seasonal) + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
        seasonals[idx % SEASON_LENGTH] = gamma * (actual - level) + (1 - gamma) * seasonal

    forecasts: List[float] = []
    for step in range(1, horizon + 1):
        seasonal = seasonals[(len(series) + step - 1) % SEASON_LENGTH]
        value = level + step * trend + seasonal
        if floor is not None:
            value = max(floor, value)
        if ceiling is not None:
            value = min(ceiling, value)
        forecasts.append(value)
    return forecasts


def _initial_seasonals(series: List[float]) -> List[float]:
    season_averages = []
    for offset in range(0, len(series), SEASON_LENGTH):
        chunk = series[offset : offset + SEASON_LENGTH]
        if len(chunk) == SEASON_LENGTH:
            season_averages.append(sum(chunk) / SEASON_LENGTH)
    seasonals: List[float] = []
    for idx in range(SEASON_LENGTH):
        values = []
        for season_idx, average in enumerate(season_averages):
            values.append(series[season_idx * SEASON_LENGTH + idx] - average)
        seasonals.append(sum(values) / max(1, len(values)))
    return seasonals


def _simple_growth_forecast(
    series: List[float],
    horizon: int,
    *,
    floor: float | None = None,
    ceiling: float | None = None,
) -> List[float]:
    if not series:
        return [0.0 for _ in range(horizon)]
    if len(series) == 1:
        base = series[-1]
        return [base for _ in range(horizon)]
    avg_step = (series[-1] - series[0]) / (len(series) - 1)
    start = series[-1]
    output = []
    for step in range(1, horizon + 1):
        value = start + step * avg_step
        if floor is not None:
            value = max(floor, value)
        if ceiling is not None:
            value = min(ceiling, value)
        output.append(value)
    return output


def _runway_months(closing_cash: float, ebitda: float) -> float:
    if ebitda >= 0:
        return 99.0
    burn = abs(ebitda)
    if burn == 0:
        return 99.0
    return max(0.0, closing_cash / burn)


def _to_float(value: str) -> float:
    return float(str(value).replace(",", "").strip())


def _parse_pct(value: str) -> float:
    raw = str(value).strip().replace("%", "")
    return float(raw) / 100.0


def _ensure_node_modules_link(repo_root: Path) -> None:
    bundled_node_modules = Path(
        "/Users/cubiczan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
    )
    target = repo_root / "node_modules"
    if target.exists() or target.is_symlink():
        return
    target.symlink_to(bundled_node_modules, target_is_directory=True)


def _resolve_node_path() -> str:
    bundled = "/Users/cubiczan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    if os.path.exists(bundled):
        return bundled
    discovered = shutil.which("node")
    if discovered:
        return discovered
    raise RuntimeError("Node.js runtime not found for workbook export.")
