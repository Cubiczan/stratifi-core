"""AP cash and payables optimizer."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Iterable, List, Sequence

from cme.chp.models import DecisionCase, Dossier, FoundationAttack, FoundationDisclosure


REQUIRED_COLUMNS = {
    "invoice_id",
    "vendor",
    "spend_category",
    "invoice_date",
    "due_date",
    "terms_days",
    "amount",
    "currency",
    "status",
    "po_number",
    "payment_terms_text",
}


@dataclass
class APInvoice:
    invoice_id: str
    vendor: str
    spend_category: str
    invoice_date: date
    due_date: date | None
    terms_days: int
    amount: float
    currency: str
    status: str
    po_number: str
    payment_terms_text: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["invoice_date"] = self.invoice_date.isoformat()
        data["due_date"] = self.due_date.isoformat() if self.due_date else None
        return data


@dataclass
class PaymentRecommendation:
    invoice_id: str
    vendor: str
    pay_date: str
    amount: float
    rationale: str
    priority_score: float
    overdue_risk: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeferredInvoice:
    invoice_id: str
    vendor: str
    amount: float
    defer_reason: str
    risk_level: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NegotiationTarget:
    vendor: str
    suggested_move: str
    expected_cash_impact: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DraftMessage:
    vendor: str
    email_subject: str
    email_body: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgingBucket:
    label: str
    amount: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WeeklyOutflowPoint:
    week_label: str
    amount: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VendorConcentrationPoint:
    vendor: str
    open_balance: float
    cumulative_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class APOptimizerResult:
    as_of_date: str
    cash_available: float
    max_vendors: int
    avoid_overdue: bool
    strategic_vendors: List[str]
    aging_buckets: List[AgingBucket] = field(default_factory=list)
    weekly_due_outflow: List[WeeklyOutflowPoint] = field(default_factory=list)
    vendor_concentration: List[VendorConcentrationPoint] = field(default_factory=list)
    recommended_payments: List[PaymentRecommendation] = field(default_factory=list)
    deferred_invoices: List[DeferredInvoice] = field(default_factory=list)
    negotiation_targets: List[NegotiationTarget] = field(default_factory=list)
    draft_messages: List[DraftMessage] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    questions_needed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of_date": self.as_of_date,
            "cash_available": self.cash_available,
            "max_vendors": self.max_vendors,
            "avoid_overdue": self.avoid_overdue,
            "strategic_vendors": self.strategic_vendors,
            "aging_buckets": [item.to_dict() for item in self.aging_buckets],
            "weekly_due_outflow": [item.to_dict() for item in self.weekly_due_outflow],
            "vendor_concentration": [item.to_dict() for item in self.vendor_concentration],
            "recommended_payments": [item.to_dict() for item in self.recommended_payments],
            "deferred_invoices": [item.to_dict() for item in self.deferred_invoices],
            "negotiation_targets": [item.to_dict() for item in self.negotiation_targets],
            "draft_messages": [item.to_dict() for item in self.draft_messages],
            "warnings": self.warnings,
            "assumptions": self.assumptions,
            "questions_needed": self.questions_needed,
        }


def load_ap_invoices_csv(path: str | Path) -> tuple[List[APInvoice], List[str]]:
    rows: List[APInvoice] = []
    warnings: List[str] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = {name.strip().lower() for name in (reader.fieldnames or [])}
        missing = REQUIRED_COLUMNS - fieldnames
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
        for idx, raw in enumerate(reader, start=2):
            due_date_raw = raw["due_date"].strip()
            due_date = _parse_date(due_date_raw) if due_date_raw else None
            if due_date is None:
                warnings.append(f"row {idx}: missing due_date for invoice {raw['invoice_id']}")
            amount = _to_float(raw["amount"])
            if amount <= 0:
                warnings.append(f"row {idx}: non-positive amount for invoice {raw['invoice_id']}")
            invoice = APInvoice(
                invoice_id=raw["invoice_id"].strip(),
                vendor=raw["vendor"].strip(),
                spend_category=raw["spend_category"].strip(),
                invoice_date=_parse_date(raw["invoice_date"]),
                due_date=due_date,
                terms_days=int(_to_float(raw["terms_days"])),
                amount=amount,
                currency=raw["currency"].strip(),
                status=raw["status"].strip(),
                po_number=raw["po_number"].strip(),
                payment_terms_text=raw["payment_terms_text"].strip(),
            )
            rows.append(invoice)
    return rows, warnings


def optimize_ap_payments(
    invoices: Sequence[APInvoice],
    *,
    cash_available: float,
    avoid_overdue: bool = True,
    strategic_vendors: Sequence[str] | None = None,
    max_vendors: int = 10,
    as_of_date: date | None = None,
) -> APOptimizerResult:
    as_of_date = as_of_date or date.today()
    strategic_set = {item.strip().lower() for item in (strategic_vendors or []) if item.strip()}
    open_invoices = [row for row in invoices if row.status.lower() in {"open", "approved", "pending"}]

    warnings = _data_quality_warnings(open_invoices)
    aging_buckets = _build_aging_buckets(open_invoices, as_of_date)
    weekly_due = _build_weekly_due_outflow(open_invoices, as_of_date)
    vendor_concentration = _build_vendor_concentration(open_invoices)

    ranked = sorted(
        (_score_invoice(row, as_of_date, avoid_overdue, strategic_set) for row in open_invoices),
        key=lambda item: item["priority_score"],
        reverse=True,
    )

    selected: List[dict[str, Any]] = []
    selected_vendors: set[str] = set()
    used_cash = 0.0
    for item in ranked:
        invoice = item["invoice"]
        vendor_key = invoice.vendor.lower()
        if vendor_key not in selected_vendors and len(selected_vendors) >= max_vendors:
            continue
        if used_cash + invoice.amount > cash_available:
            continue
        selected.append(item)
        selected_vendors.add(vendor_key)
        used_cash += invoice.amount

    selected_ids = {item["invoice"].invoice_id for item in selected}
    recommendations = [
        PaymentRecommendation(
            invoice_id=item["invoice"].invoice_id,
            vendor=item["invoice"].vendor,
            pay_date=_recommended_pay_date(item["invoice"], as_of_date, avoid_overdue).isoformat(),
            amount=item["invoice"].amount,
            rationale=item["rationale"],
            priority_score=round(item["priority_score"], 1),
            overdue_risk=item["risk"],
        )
        for item in selected
    ]

    deferred = [
        DeferredInvoice(
            invoice_id=invoice.invoice_id,
            vendor=invoice.vendor,
            amount=invoice.amount,
            defer_reason=_defer_reason(invoice, as_of_date, avoid_overdue, strategic_set, invoice.invoice_id in selected_ids),
            risk_level=_risk_level(invoice, as_of_date),
        )
        for invoice in open_invoices
        if invoice.invoice_id not in selected_ids
    ]
    deferred.sort(key=lambda item: (item.risk_level != "HIGH", -item.amount))

    negotiation_targets = _build_negotiation_targets(deferred)
    draft_messages = _build_draft_messages(negotiation_targets)

    assumptions = [
        f"Model assumes {cash_available:,.0f} cash is the true weekly AP budget.",
        "All invoices are assumed payable in the stated currency without FX constraints.",
        "Invoices without due dates are treated as medium-risk exceptions rather than auto-pay items.",
    ]
    questions_needed = []
    if not strategic_set:
        questions_needed.append("Which vendors are strategic enough to prioritize despite lower invoice urgency?")
    if any(invoice.due_date is None for invoice in open_invoices):
        questions_needed.append("Which invoices with missing due dates should be treated as near-term obligations?")

    return APOptimizerResult(
        as_of_date=as_of_date.isoformat(),
        cash_available=cash_available,
        max_vendors=max_vendors,
        avoid_overdue=avoid_overdue,
        strategic_vendors=sorted(strategic_set),
        aging_buckets=aging_buckets,
        weekly_due_outflow=weekly_due,
        vendor_concentration=vendor_concentration,
        recommended_payments=recommendations,
        deferred_invoices=deferred[:20],
        negotiation_targets=negotiation_targets,
        draft_messages=draft_messages,
        warnings=warnings,
        assumptions=assumptions,
        questions_needed=questions_needed,
    )


def build_ap_optimizer_case(
    result: APOptimizerResult,
    *,
    owner: str = "cfo",
    origin_system: str = "Claude",
    origin_model: str = "GPT-5.4",
    partner_system: str = "Partner",
    partner_model: str = "GPT-5-equivalent",
) -> tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    high_risk_deferrals = [item for item in result.deferred_invoices if item.risk_level == "HIGH"]
    dossier = Dossier(
        core_problem="Prioritize AP payments under cash constraints without creating avoidable overdue risk or vendor stress.",
        goal_state=[
            "Payment plan stays within the cash cap",
            "Overdue risk is made explicit rather than hidden in manual judgment",
            "Strategic-vendor exceptions are visible and defensible",
        ],
        current_state=[
            f"Cash available this week: ${result.cash_available:,.0f}",
            f"Recommended payments: {len(result.recommended_payments)} invoices",
            f"Deferred high-risk invoices: {len(high_risk_deferrals)}",
        ],
        prior_decisions=[],
        constraints=[
            "Do not exceed the weekly AP cash budget",
            "Honor max-vendor concentration limits in the recommendation set",
            "Make overdue risk explicit for every deferred invoice",
        ],
        unknowns=[
            "Supplier leverage may vary beyond what the invoice file shows",
            "Some invoices may have operational dependencies not visible in finance data",
        ],
        scope=[
            "Invoice prioritization",
            "Deferral risk review",
            "Negotiation target selection",
        ],
        origin_direction=[
            "Prefer paying the invoices that avoid the most near-term risk per dollar spent",
            "Keep strategic-vendor overrides explicit rather than baked into hidden heuristics",
        ],
        structural_vulnerabilities=[
            "Invoice-level optimization can miss operational dependencies that are not tagged in the data",
            "A tight cash cap can make the recommendation look optimal while simply pushing risk into the next cycle",
        ],
    )
    case = DecisionCase(
        decision_id=f"ap-opt-{result.as_of_date}",
        title=f"AP cash and payables optimizer {result.as_of_date}",
        domain="ap_optimizer",
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
            "The invoice file captures the real operational urgency behind each payable",
            "Strategic-vendor preferences are sufficient to represent non-financial exceptions",
            "The weekly cash cap is accurate enough to support a binding payment plan",
        ],
        invalidation_conditions=[
            "Hidden supplier or operational dependencies make a deferred invoice costlier than its score suggests",
            "The real cash envelope changes after the recommendation is issued",
        ],
        key_vulnerability="The optimizer is most exposed where finance-visible urgency differs from operational urgency.",
    )
    score = 85 - min(12, len(high_risk_deferrals) * 2) - min(6, len(result.warnings))
    attack = FoundationAttack(
        assumption_attacks=[
            "The scoring model can underweight vendors that are strategically important but poorly tagged in the source file.",
            "A recommendation that fits the cash cap can still create hidden downstream disruption if deferrals hit critical suppliers.",
            "Data-quality gaps like missing due dates can make the output look more certain than it really is.",
        ],
        invalidation_exploitation=[
            "One misclassified strategic invoice can turn a 'safe' deferral into an operating incident.",
            "A smaller real cash envelope can reopen the entire recommendation set immediately.",
        ],
        vulnerability_strike="The plan only holds if finance data is a good proxy for supplier criticality and near-term cash truth.",
        foundation_score=max(60, min(92, score)),
        attack_summary="The optimizer is useful for structuring weekly AP decisions, but it should be treated as a guided plan that still needs informed exception handling.",
    )
    dossier.foundation_score = attack.foundation_score
    dossier.prior_round_summary = [f"High-risk deferrals: {len(high_risk_deferrals)}"]
    return case, disclosure, attack


def render_ap_optimizer_markdown(result: APOptimizerResult) -> str:
    lines = [
        "# AP Cash & Payables Optimizer",
        f"**As Of:** {result.as_of_date}",
        f"**Cash Available:** ${result.cash_available:,.0f}",
        f"**Max Vendors:** {result.max_vendors}",
        "",
        "## Recommended Payments",
    ]
    for item in result.recommended_payments:
        lines.append(
            f"- {item.invoice_id} | {item.vendor} | ${item.amount:,.0f} | pay {item.pay_date} | "
            f"score={item.priority_score:.1f} | {item.rationale}"
        )
    lines.extend(["", "## Deferred Invoices"])
    for item in result.deferred_invoices[:10]:
        lines.append(
            f"- {item.invoice_id} | {item.vendor} | ${item.amount:,.0f} | risk={item.risk_level} | {item.defer_reason}"
        )
    lines.extend(["", "## Negotiation Targets"])
    for item in result.negotiation_targets:
        lines.append(
            f"- {item.vendor} | {item.suggested_move} | expected cash impact ${item.expected_cash_impact:,.0f}"
        )
    return "\n".join(lines)


def export_ap_optimizer_workbook(
    result: APOptimizerResult,
    *,
    session_summary: str,
    output_path: str | Path,
) -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    builder_path = repo_root / "tools" / "build_ap_optimizer_workbook.mjs"
    node_path = _resolve_node_path()
    _ensure_node_modules_link(repo_root)
    payload = {
        "optimizer": result.to_dict(),
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


def _data_quality_warnings(invoices: Sequence[APInvoice]) -> List[str]:
    warnings: List[str] = []
    if any(item.due_date is None for item in invoices):
        warnings.append("Some invoices are missing due dates and may be under-ranked.")
    if any(item.amount > 250_000 for item in invoices):
        warnings.append("One or more invoices are unusually large and may need manual review.")
    if any(item.currency.upper() != "USD" for item in invoices):
        warnings.append("Non-USD invoices were treated as nominal amounts without FX conversion.")
    return warnings


def _build_aging_buckets(invoices: Sequence[APInvoice], as_of_date: date) -> List[AgingBucket]:
    buckets = {
        "Not due": 0.0,
        "1-15 overdue": 0.0,
        "16-30 overdue": 0.0,
        "31-60 overdue": 0.0,
        "60+ overdue": 0.0,
    }
    for item in invoices:
        if item.due_date is None:
            continue
        days = (as_of_date - item.due_date).days
        if days < 1:
            buckets["Not due"] += item.amount
        elif days <= 15:
            buckets["1-15 overdue"] += item.amount
        elif days <= 30:
            buckets["16-30 overdue"] += item.amount
        elif days <= 60:
            buckets["31-60 overdue"] += item.amount
        else:
            buckets["60+ overdue"] += item.amount
    return [AgingBucket(label=key, amount=round(value, 2)) for key, value in buckets.items()]


def _build_weekly_due_outflow(invoices: Sequence[APInvoice], as_of_date: date) -> List[WeeklyOutflowPoint]:
    weeks: Dict[str, float] = defaultdict(float)
    start = as_of_date
    for offset in range(6):
        week_start = start + timedelta(days=offset * 7)
        label = week_start.isoformat()
        weeks[label] = 0.0
    for item in invoices:
        if item.due_date is None:
            continue
        delta_days = (item.due_date - as_of_date).days
        if 0 <= delta_days < 42:
            week_start = as_of_date + timedelta(days=(delta_days // 7) * 7)
            weeks[week_start.isoformat()] += item.amount
    return [WeeklyOutflowPoint(week_label=label, amount=round(amount, 2)) for label, amount in sorted(weeks.items())]


def _build_vendor_concentration(invoices: Sequence[APInvoice]) -> List[VendorConcentrationPoint]:
    balances: Dict[str, float] = defaultdict(float)
    for item in invoices:
        balances[item.vendor] += item.amount
    total = sum(balances.values()) or 1.0
    cumulative = 0.0
    output: List[VendorConcentrationPoint] = []
    for vendor, balance in sorted(balances.items(), key=lambda item: item[1], reverse=True)[:10]:
        cumulative += balance
        output.append(
            VendorConcentrationPoint(
                vendor=vendor,
                open_balance=round(balance, 2),
                cumulative_pct=round(cumulative / total, 4),
            )
        )
    return output


def _score_invoice(
    invoice: APInvoice,
    as_of_date: date,
    avoid_overdue: bool,
    strategic_vendors: set[str],
) -> Dict[str, Any]:
    days_to_due = 999 if invoice.due_date is None else (invoice.due_date - as_of_date).days
    overdue_days = 0 if invoice.due_date is None else max(0, (as_of_date - invoice.due_date).days)
    strategic = invoice.vendor.lower() in strategic_vendors
    score = 20.0
    if invoice.due_date is None:
        score += 5
    elif overdue_days > 0:
        score += 55 + min(20, overdue_days)
    elif days_to_due <= 3:
        score += 35
    elif days_to_due <= 7:
        score += 24
    elif days_to_due <= 14:
        score += 14
    if avoid_overdue and overdue_days > 0:
        score += 15
    if strategic:
        score += 12
    if invoice.spend_category.lower() in {"infrastructure", "payroll support", "inventory", "logistics"}:
        score += 8
    score += min(10, invoice.amount / 50_000)

    if overdue_days > 30:
        risk = "HIGH"
    elif overdue_days > 0 or days_to_due <= 5:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    rationale_parts = []
    if overdue_days > 0:
        rationale_parts.append(f"{overdue_days} day(s) overdue")
    elif invoice.due_date is not None:
        rationale_parts.append(f"due in {max(days_to_due, 0)} day(s)")
    else:
        rationale_parts.append("missing due date requires review")
    if strategic:
        rationale_parts.append("strategic vendor")
    if invoice.spend_category:
        rationale_parts.append(invoice.spend_category.lower())

    return {
        "invoice": invoice,
        "priority_score": score,
        "risk": risk,
        "rationale": ", ".join(rationale_parts),
    }


def _recommended_pay_date(invoice: APInvoice, as_of_date: date, avoid_overdue: bool) -> date:
    if invoice.due_date is None:
        return as_of_date + timedelta(days=2)
    if avoid_overdue and invoice.due_date <= as_of_date:
        return as_of_date
    return min(invoice.due_date, as_of_date + timedelta(days=7))


def _defer_reason(
    invoice: APInvoice,
    as_of_date: date,
    avoid_overdue: bool,
    strategic_vendors: set[str],
    selected: bool,
) -> str:
    if selected:
        return "Included in recommended payment set."
    if invoice.due_date is None:
        return "Missing due date kept this invoice out of the auto-pay set."
    days = (invoice.due_date - as_of_date).days
    if avoid_overdue and days < 0:
        return "Cash cap prevented paying every overdue invoice; this item should be reviewed manually."
    if invoice.vendor.lower() not in strategic_vendors and days > 7:
        return "Not immediately due and not tagged as a strategic-vendor exception."
    return "Lower risk-adjusted priority than the invoices selected under the current cash cap."


def _risk_level(invoice: APInvoice, as_of_date: date) -> str:
    if invoice.due_date is None:
        return "MEDIUM"
    overdue = (as_of_date - invoice.due_date).days
    if overdue > 15:
        return "HIGH"
    if overdue > 0 or (invoice.due_date - as_of_date).days <= 5:
        return "MEDIUM"
    return "LOW"


def _build_negotiation_targets(deferred: Sequence[DeferredInvoice]) -> List[NegotiationTarget]:
    vendor_totals: Dict[str, float] = defaultdict(float)
    vendor_risk: Dict[str, str] = {}
    for item in deferred:
        vendor_totals[item.vendor] += item.amount
        vendor_risk[item.vendor] = max(vendor_risk.get(item.vendor, "LOW"), item.risk_level, key=_risk_rank)
    targets: List[NegotiationTarget] = []
    for vendor, total in sorted(vendor_totals.items(), key=lambda item: item[1], reverse=True)[:5]:
        risk = vendor_risk[vendor]
        move = "extend terms by 15 days" if risk == "HIGH" else "split payment across two weeks"
        targets.append(
            NegotiationTarget(
                vendor=vendor,
                suggested_move=move,
                expected_cash_impact=round(total * (0.5 if risk == "LOW" else 0.7), 2),
            )
        )
    return targets


def _build_draft_messages(targets: Sequence[NegotiationTarget]) -> List[DraftMessage]:
    messages: List[DraftMessage] = []
    for item in targets:
        messages.append(
            DraftMessage(
                vendor=item.vendor,
                email_subject=f"Payment scheduling discussion for upcoming AP cycle",
                email_body=(
                    f"Hi {item.vendor} team,\n\n"
                    f"We are reviewing this week's AP cycle and would like to discuss a {item.suggested_move}. "
                    f"Our goal is to keep the relationship strong while aligning payment timing with our near-term cash plan. "
                    f"Please let us know whether we can work through the proposed schedule this week.\n\n"
                    "Best,\nFinance"
                ),
            )
        )
    return messages


def _risk_rank(value: str) -> int:
    return {"LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(value, 0)


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def _to_float(value: str) -> float:
    return float(str(value).replace(",", "").strip())


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
