"""13-week cash forecast engine."""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from cme.chp.models import DecisionCase, Dossier, FoundationAttack, FoundationDisclosure


SEASONALITY_BY_MONTH = {
    9: 1.05,
    10: 0.97,
    11: 1.12,
}


@dataclass
class OpeningCashRow:
    account: str
    amount_usd: float


@dataclass
class SalesRow:
    date: date
    channel: str
    amount_usd: float


@dataclass
class APRow:
    date: date
    vendor: str
    category: str
    amount_usd: float


@dataclass
class PayrollRow:
    date: date
    amount_usd: float


@dataclass
class OutflowRow:
    date: date
    category: str
    vendor: str
    amount_usd: float
    type: str


@dataclass
class ForecastSettings:
    as_of_date: date
    horizon_weeks: int = 13
    jitter_pct: float = 0.0
    min_cash_warning: float = 0.0


@dataclass
class InflowWeek:
    week_ending: date
    channel: str
    cash_in_usd: float

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["week_ending"] = self.week_ending.isoformat()
        return data


@dataclass
class OutflowWeek:
    week_ending: date
    category: str
    cash_out_usd: float

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["week_ending"] = self.week_ending.isoformat()
        return data


@dataclass
class WeeklySummaryRow:
    week_ending: date
    opening_balance: float
    cash_in: float
    cash_out: float
    net_cash_flow: float
    closing_balance: float
    risk_flag: str = "OK"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["week_ending"] = self.week_ending.isoformat()
        return data


@dataclass
class DriverDetail:
    channel: str
    baseline: float
    trend_pct: float
    seasonality_multiplier: float
    jitter_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CashForecast13WResult:
    settings: ForecastSettings
    opening_cash_total: float
    inflows_by_week: List[InflowWeek] = field(default_factory=list)
    outflows_by_week: List[OutflowWeek] = field(default_factory=list)
    weekly_summary: List[WeeklySummaryRow] = field(default_factory=list)
    driver_details: List[DriverDetail] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "settings": {
                "as_of_date": self.settings.as_of_date.isoformat(),
                "horizon_weeks": self.settings.horizon_weeks,
                "jitter_pct": self.settings.jitter_pct,
                "min_cash_warning": self.settings.min_cash_warning,
            },
            "opening_cash_total": self.opening_cash_total,
            "inflows_by_week": [row.to_dict() for row in self.inflows_by_week],
            "outflows_by_week": [row.to_dict() for row in self.outflows_by_week],
            "weekly_summary": [row.to_dict() for row in self.weekly_summary],
            "driver_details": [row.to_dict() for row in self.driver_details],
            "risk_flags": self.risk_flags,
        }


@dataclass
class CashForecastWorkbookInput:
    opening_cash: List[OpeningCashRow]
    settings: ForecastSettings
    sales: List[SalesRow]
    ap_rows: List[APRow]
    payroll_rows: List[PayrollRow]
    outflow_rows: List[OutflowRow]


def load_opening_cash_csv(path: str | Path) -> List[OpeningCashRow]:
    return [
        OpeningCashRow(account=row["Account"].strip(), amount_usd=_to_float(row["AmountUSD"]))
        for row in _read_csv(path)
    ]


def load_settings_csv(path: str | Path) -> ForecastSettings:
    items = {row["Key"].strip(): row["Value"].strip() for row in _read_csv(path)}
    return ForecastSettings(
        as_of_date=_parse_date(items["AsOfDate"]),
        horizon_weeks=int(items.get("HorizonWeeks", "13")),
        jitter_pct=float(items.get("JitterPct", "0")),
        min_cash_warning=float(items.get("MinCashWarning", "0")),
    )


def load_sales_csv(path: str | Path) -> List[SalesRow]:
    return [
        SalesRow(
            date=_parse_date(row["Date"]),
            channel=row["Channel"].strip(),
            amount_usd=_to_float(row["AmountUSD"]),
        )
        for row in _read_csv(path)
    ]


def load_ap_csv(path: str | Path) -> List[APRow]:
    return [
        APRow(
            date=_parse_date(row["Date"]),
            vendor=row["Vendor"].strip(),
            category=row["Category"].strip(),
            amount_usd=_to_float(row["AmountUSD"]),
        )
        for row in _read_csv(path)
    ]


def load_payroll_csv(path: str | Path) -> List[PayrollRow]:
    return [
        PayrollRow(
            date=_parse_date(row["Date"]),
            amount_usd=_to_float(row["AmountUSD"]),
        )
        for row in _read_csv(path)
    ]


def load_outflows_csv(path: str | Path) -> List[OutflowRow]:
    return [
        OutflowRow(
            date=_parse_date(row["Date"]),
            category=row["Category"].strip(),
            vendor=row["Vendor"].strip(),
            amount_usd=_to_float(row["AmountUSD"]),
            type=row["Type"].strip(),
        )
        for row in _read_csv(path)
    ]


def load_cash_forecast_workbook(path: str | Path) -> CashForecastWorkbookInput:
    repo_root = Path(__file__).resolve().parents[3]
    extractor_path = repo_root / "tools" / "extract_cash_forecast_input.mjs"
    node_path = _resolve_node_path()
    _ensure_node_modules_link(repo_root)

    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False, encoding="utf-8") as handle:
        output_json = Path(handle.name)

    try:
        subprocess.run(
            [node_path, str(extractor_path), str(path), str(output_json)],
            check=True,
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        payload = json.loads(output_json.read_text(encoding="utf-8"))
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr or exc.stdout or "Workbook import failed.") from exc
    finally:
        output_json.unlink(missing_ok=True)

    opening_cash = [
        OpeningCashRow(account=row["account"], amount_usd=float(row["amount_usd"]))
        for row in payload["opening_cash"]
    ]
    settings = ForecastSettings(
        as_of_date=_parse_date(payload["settings"]["as_of_date"]),
        horizon_weeks=int(payload["settings"]["horizon_weeks"]),
        jitter_pct=float(payload["settings"]["jitter_pct"]),
        min_cash_warning=float(payload["settings"]["min_cash_warning"]),
    )
    sales = [
        SalesRow(date=_parse_date(row["date"]), channel=row["channel"], amount_usd=float(row["amount_usd"]))
        for row in payload["sales"]
    ]
    ap_rows = [
        APRow(
            date=_parse_date(row["date"]),
            vendor=row["vendor"],
            category=row["category"],
            amount_usd=float(row["amount_usd"]),
        )
        for row in payload["ap_rows"]
    ]
    payroll_rows = [
        PayrollRow(date=_parse_date(row["date"]), amount_usd=float(row["amount_usd"]))
        for row in payload["payroll_rows"]
    ]
    outflow_rows = [
        OutflowRow(
            date=_parse_date(row["date"]),
            category=row["category"],
            vendor=row["vendor"],
            amount_usd=float(row["amount_usd"]),
            type=row["type"],
        )
        for row in payload["outflow_rows"]
    ]
    return CashForecastWorkbookInput(
        opening_cash=opening_cash,
        settings=settings,
        sales=sales,
        ap_rows=ap_rows,
        payroll_rows=payroll_rows,
        outflow_rows=outflow_rows,
    )


def build_13_week_cash_forecast(
    *,
    opening_cash: List[OpeningCashRow],
    settings: ForecastSettings,
    sales: List[SalesRow],
    ap_rows: List[APRow],
    payroll_rows: List[PayrollRow],
    outflow_rows: List[OutflowRow],
) -> CashForecast13WResult:
    week_endings = _forecast_week_endings(settings.as_of_date, settings.horizon_weeks)
    inflows, driver_details = _forecast_inflows(sales, week_endings, settings.jitter_pct)
    outflows = _forecast_outflows(ap_rows, payroll_rows, outflow_rows, week_endings)
    opening_total = sum(item.amount_usd for item in opening_cash)
    weekly_summary, risk_flags = _roll_forward(opening_total, inflows, outflows, settings.min_cash_warning)
    return CashForecast13WResult(
        settings=settings,
        opening_cash_total=opening_total,
        inflows_by_week=inflows,
        outflows_by_week=outflows,
        weekly_summary=weekly_summary,
        driver_details=driver_details,
        risk_flags=risk_flags,
    )


def build_cash_forecast_case(
    result: CashForecast13WResult,
    *,
    owner: str = "cfo",
    origin_system: str = "Claude",
    origin_model: str = "GPT-5.4",
    partner_system: str = "Partner",
    partner_model: str = "GPT-5-equivalent",
) -> tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    low_weeks = [row for row in result.weekly_summary if row.risk_flag != "OK"]
    min_balance = min(row.closing_balance for row in result.weekly_summary)
    max_outflow = max((row.cash_out for row in result.weekly_summary), default=0.0)
    dossier = Dossier(
        core_problem=f"Harden the 13-week cash forecast and identify the weeks that require action before cash pressure becomes acute.",
        goal_state=[
            "13 weekly balances are forecast from source files",
            "Red-zone weeks are explicitly flagged",
            "Cash timing assumptions are challenged before the forecast is trusted",
        ],
        current_state=[
            f"Opening cash is {opening_fmt(result.opening_cash_total)}",
            f"Minimum projected closing balance is {opening_fmt(min_balance)}",
            f"{len(low_weeks)} week(s) are currently flagged for cash risk",
        ],
        constraints=[
            "Do not double count AP and outflow rows",
            "Keep payroll rows regardless of overlap",
            "Roll forward must use weekly closing balance as next opening balance",
        ],
        unknowns=[
            "Collection timing outside the last 8 weeks may differ from baseline",
            "Management interventions may change payment timing during the forecast horizon",
        ],
        scope=[
            "Forecast logic",
            "Risk flag review",
            "Action recommendation hardening",
        ],
        origin_direction=[
            "Prefer conservative liquidity interpretation when timing is ambiguous",
            "Escalate weeks that breach minimum cash thresholds",
        ],
        structural_vulnerabilities=[
            "Short-term inflow forecasts can overstate receipts if trailing patterns break",
            "Outflow timing can change materially when AP is manually managed",
        ],
    )
    case = DecisionCase(
        decision_id=f"cash-13w-{result.settings.as_of_date.isoformat()}",
        title=f"13-week cash forecast from {result.settings.as_of_date.isoformat()}",
        domain="cashflow_13w",
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
            "Trailing 4-week channel baselines are representative of the next 13 weeks",
            "Recorded AP and outflows capture the true near-term cash obligations",
            "Seasonality and timing adjustments are directionally correct enough for decisions",
        ],
        invalidation_conditions=[
            "Collections or sales mix shift materially away from recent history",
            "Management changes payment timing outside the forecasted dates",
        ],
        key_vulnerability="The forecast is most fragile where receipt timing is assumed rather than contracted.",
    )
    score = max(62, 85 - len(low_weeks) * 4 - (5 if max_outflow > result.opening_cash_total * 0.4 else 0))
    attack = FoundationAttack(
        assumption_attacks=[
            "Recent channel performance may not be a safe predictor if demand or payout timing is changing.",
            "AP and outflow files may still omit discretionary or manually delayed payments.",
            "Seasonality is simple and may understate volatility around large receipts or one-offs.",
        ],
        invalidation_exploitation=[
            "A single large receipt delay can turn a safe week into a red week.",
            "A payment acceleration can invalidate the assumed cash runway immediately.",
        ],
        vulnerability_strike="The forecast can look healthy until a timing shock exposes how thin the true liquidity buffer is.",
        foundation_score=score,
        attack_summary="The forecast is directionally useful, but timing risk dominates precision risk. Red-zone weeks should be reviewed as management decisions, not passive projections.",
    )
    dossier.foundation_score = score
    dossier.prior_round_summary = [f"Flagged weeks: {', '.join(row.week_ending.isoformat() for row in low_weeks[:5]) or 'none'}"]
    return case, disclosure, attack


def render_cash_forecast_markdown(result: CashForecast13WResult) -> str:
    lines = [
        "# 13-Week Cash Forecast Engine",
        f"**As Of:** {result.settings.as_of_date.isoformat()}",
        f"**Opening Cash:** {opening_fmt(result.opening_cash_total)}",
        "",
        "## Weekly Summary",
    ]
    for row in result.weekly_summary:
        lines.append(
            f"- {row.week_ending.isoformat()} | open={opening_fmt(row.opening_balance)} | "
            f"in={opening_fmt(row.cash_in)} | out={opening_fmt(row.cash_out)} | "
            f"net={opening_fmt(row.net_cash_flow)} | close={opening_fmt(row.closing_balance)} | risk={row.risk_flag}"
        )
    lines.append("")
    lines.append("## Risk Flags")
    for flag in result.risk_flags or ["No risk flags raised."]:
        lines.append(f"- {flag}")
    return "\n".join(lines)


def export_cash_forecast_workbook(
    result: CashForecast13WResult,
    *,
    session_summary: str,
    output_path: str | Path,
) -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    builder_path = repo_root / "tools" / "build_cash_forecast_workbook.mjs"
    node_path = _resolve_node_path()
    _ensure_node_modules_link(repo_root)

    payload = {
        "forecast": result.to_dict(),
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


def export_cash_forecast_input_template(
    *,
    output_path: str | Path,
    opening_cash: List[OpeningCashRow] | None = None,
    settings: ForecastSettings | None = None,
    sales: List[SalesRow] | None = None,
    ap_rows: List[APRow] | None = None,
    payroll_rows: List[PayrollRow] | None = None,
    outflow_rows: List[OutflowRow] | None = None,
) -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    builder_path = repo_root / "tools" / "build_cash_forecast_input_template.mjs"
    node_path = _resolve_node_path()
    _ensure_node_modules_link(repo_root)

    template_payload = {
        "opening_cash": [
            {"account": row.account, "amount_usd": row.amount_usd}
            for row in (opening_cash or [OpeningCashRow(account="Operating Account", amount_usd=500000.0)])
        ],
        "settings": {
            "as_of_date": (settings.as_of_date.isoformat() if settings else date.today().isoformat()),
            "horizon_weeks": settings.horizon_weeks if settings else 13,
            "jitter_pct": settings.jitter_pct if settings else 0.0,
            "min_cash_warning": settings.min_cash_warning if settings else 150000.0,
        },
        "sales": [
            {"date": row.date.isoformat(), "channel": row.channel, "amount_usd": row.amount_usd}
            for row in (sales or [])
        ],
        "ap_rows": [
            {"date": row.date.isoformat(), "vendor": row.vendor, "category": row.category, "amount_usd": row.amount_usd}
            for row in (ap_rows or [])
        ],
        "payroll_rows": [
            {"date": row.date.isoformat(), "amount_usd": row.amount_usd}
            for row in (payroll_rows or [])
        ],
        "outflow_rows": [
            {
                "date": row.date.isoformat(),
                "category": row.category,
                "vendor": row.vendor,
                "amount_usd": row.amount_usd,
                "type": row.type,
            }
            for row in (outflow_rows or [])
        ],
    }
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(template_payload, handle, indent=2)
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
        raise RuntimeError(exc.stderr or exc.stdout or "Input template export failed.") from exc
    finally:
        temp_json.unlink(missing_ok=True)

    return output_file


def _forecast_week_endings(as_of_date: date, horizon_weeks: int) -> List[date]:
    offset = (4 - as_of_date.weekday()) % 7
    first_friday = as_of_date + timedelta(days=offset)
    return [first_friday + timedelta(days=7 * idx) for idx in range(horizon_weeks)]


def _forecast_inflows(
    sales: List[SalesRow],
    week_endings: List[date],
    jitter_pct: float,
) -> tuple[List[InflowWeek], List[DriverDetail]]:
    by_channel: Dict[str, List[Tuple[date, float]]] = defaultdict(list)
    for row in sales:
        by_channel[row.channel].append((_week_ending(row.date), row.amount_usd))

    inflows: List[InflowWeek] = []
    drivers: List[DriverDetail] = []
    for channel, entries in by_channel.items():
        weekly_series = _sum_by_week(entries)
        sorted_points = sorted(weekly_series.items())
        values = [amount for _, amount in sorted_points]
        baseline = sum(values[-4:]) / max(1, len(values[-4:]))
        trend_pct = _trend_pct(values)
        for idx, week in enumerate(week_endings):
            seasonality = SEASONALITY_BY_MONTH.get(week.month, 1.0)
            forecast = baseline * (1 + trend_pct * idx) * seasonality * (1 + jitter_pct)
            inflows.append(InflowWeek(week_ending=week, channel=channel, cash_in_usd=round(forecast, 2)))
            if idx == 0:
                drivers.append(
                    DriverDetail(
                        channel=channel,
                        baseline=round(baseline, 2),
                        trend_pct=round(trend_pct, 4),
                        seasonality_multiplier=seasonality,
                        jitter_pct=jitter_pct,
                    )
                )
    inflows.sort(key=lambda row: (row.week_ending, row.channel))
    return inflows, drivers


def _forecast_outflows(
    ap_rows: List[APRow],
    payroll_rows: List[PayrollRow],
    outflow_rows: List[OutflowRow],
    week_endings: List[date],
) -> List[OutflowWeek]:
    horizon_start = week_endings[0] - timedelta(days=6)
    horizon_end = week_endings[-1]

    ap_horizon = [row for row in ap_rows if horizon_start <= row.date <= horizon_end]
    payroll_horizon = [row for row in payroll_rows if horizon_start <= row.date <= horizon_end]
    outflow_horizon = [row for row in outflow_rows if horizon_start <= row.date <= horizon_end]

    filtered_outflows: List[OutflowRow] = []
    for outflow in outflow_horizon:
        duplicate = any(
            ap.vendor.lower() == outflow.vendor.lower()
            and abs((ap.date - outflow.date).days) <= 3
            and abs(ap.amount_usd - outflow.amount_usd) <= 100
            for ap in ap_horizon
        )
        if not duplicate:
            filtered_outflows.append(outflow)

    buckets: Dict[Tuple[date, str], float] = defaultdict(float)
    for row in ap_horizon:
        buckets[(_week_ending(row.date), row.category)] += row.amount_usd
    for row in payroll_horizon:
        buckets[(_week_ending(row.date), "Payroll")] += row.amount_usd
    for row in filtered_outflows:
        buckets[(_week_ending(row.date), row.category)] += row.amount_usd

    outflows = [
        OutflowWeek(week_ending=week, category=category, cash_out_usd=round(amount, 2))
        for (week, category), amount in sorted(buckets.items())
    ]
    return outflows


def _roll_forward(
    opening_total: float,
    inflows: List[InflowWeek],
    outflows: List[OutflowWeek],
    min_cash_warning: float,
) -> tuple[List[WeeklySummaryRow], List[str]]:
    inflow_map: Dict[date, float] = defaultdict(float)
    outflow_map: Dict[date, float] = defaultdict(float)
    for row in inflows:
        inflow_map[row.week_ending] += row.cash_in_usd
    for row in outflows:
        outflow_map[row.week_ending] += row.cash_out_usd

    weekly_summary: List[WeeklySummaryRow] = []
    risk_flags: List[str] = []
    opening = opening_total
    for week in sorted(set(list(inflow_map.keys()) + list(outflow_map.keys()))):
        cash_in = inflow_map[week]
        cash_out = outflow_map[week]
        net = cash_in - cash_out
        closing = opening + net
        risk_flag = "OK"
        if closing < 0:
            risk_flag = "CRITICAL_NEGATIVE_CASH"
            risk_flags.append(f"{week.isoformat()}: projected closing cash is negative at {opening_fmt(closing)}")
        elif closing < min_cash_warning:
            risk_flag = "LOW_CASH_WARNING"
            risk_flags.append(f"{week.isoformat()}: projected closing cash is below threshold at {opening_fmt(closing)}")
        weekly_summary.append(
            WeeklySummaryRow(
                week_ending=week,
                opening_balance=round(opening, 2),
                cash_in=round(cash_in, 2),
                cash_out=round(cash_out, 2),
                net_cash_flow=round(net, 2),
                closing_balance=round(closing, 2),
                risk_flag=risk_flag,
            )
        )
        opening = closing
    return weekly_summary, risk_flags


def _sum_by_week(entries: Iterable[Tuple[date, float]]) -> Dict[date, float]:
    out: Dict[date, float] = defaultdict(float)
    for week, amount in entries:
        out[week] += amount
    return out


def _week_ending(value: date) -> date:
    offset = (4 - value.weekday()) % 7
    return value + timedelta(days=offset)


def _trend_pct(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    xs = list(range(len(values)))
    mean_x = sum(xs) / len(xs)
    mean_y = sum(values) / len(values)
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0 or mean_y == 0:
        return 0.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / denom
    pct = slope / mean_y
    return max(-0.02, min(0.02, pct))


def _read_csv(path: str | Path) -> List[Dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _to_float(value: str) -> float:
    return float(value.replace(",", "").strip())


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def opening_fmt(value: float) -> str:
    return f"${value:,.0f}"


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
