"""Brief -> CHP DecisionCase + FoundationDisclosure + FoundationAttack.

Each CFO task type lands the inputs into the canonical CHP shape so the same
hardening pipeline runs on forecasts, investment cases, and board outputs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from cme.chp.models import DecisionCase, Dossier, FoundationAttack, FoundationDisclosure
from cme.cfo_os.briefs import (
    BoardBrief,
    CFOBrief,
    CFOTaskType,
    ForecastBrief,
    InvestmentBrief,
    SweepBrief,
)


def build_decision_case(
    brief: CFOBrief,
) -> Tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    if isinstance(brief, ForecastBrief):
        return _build_forecast_case(brief)
    if isinstance(brief, InvestmentBrief):
        return _build_investment_case(brief)
    if isinstance(brief, BoardBrief):
        return _build_board_case(brief)
    if isinstance(brief, SweepBrief):
        return _build_sweep_case(brief)
    raise TypeError(f"Unsupported brief type: {type(brief).__name__}")


def _decision_id(prefix: str, title: str) -> str:
    seed = "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-")
    return f"{prefix}-{seed[:32]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _domain_for(task: CFOTaskType) -> str:
    return {
        CFOTaskType.FORECAST: "forecast",
        CFOTaskType.INVESTMENT_CASE: "capital_allocation",
        CFOTaskType.BOARD_OUTPUT: "board_decision",
        CFOTaskType.FILING_SWEEP: "regulatory_filing_sweep",
    }[task]


def _build_forecast_case(
    brief: ForecastBrief,
) -> Tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    decision_id = brief.decision_id or _decision_id("fc", brief.title)
    growth_pct = int(round(brief.growth_assumption_pct * 100))
    churn_pct = int(round(brief.churn_assumption_pct * 100))
    dossier = Dossier(
        core_problem=brief.problem,
        goal_state=[
            f"Forecast horizon: {brief.horizon}",
            f"Runway stays >= {brief.minimum_runway_months} months at central case",
        ]
        + brief.strategic_priorities[:2],
        current_state=[
            f"Base revenue: ${brief.base_revenue_usd:,.0f}",
            f"Base opex: ${brief.base_opex_usd:,.0f}",
            f"Current runway: {brief.current_runway_months} months",
        ],
        prior_decisions=[],
        constraints=[
            f"Runway floor: {brief.minimum_runway_months} months",
            "Drivers must be auditable to source data",
        ]
        + brief.constraints,
        unknowns=[
            "Macro demand softness",
            "Hiring ramp slope",
        ],
        scope=[
            "Driver model",
            "Stress views",
            "Locked plan package",
        ],
        origin_direction=[
            "Prefer driver-based projection over top-down growth",
            "Require explicit assumption registry",
        ],
        structural_vulnerabilities=[
            "Growth and churn assumptions may compound errors",
            "Cost drivers may lag revenue without explicit lock points",
        ],
    )
    case = DecisionCase(
        decision_id=decision_id,
        title=brief.title,
        domain=_domain_for(brief.task_type),
        created_at=_now(),
        owner=brief.owner,
        high_stakes=brief.high_stakes,
        origin_system=brief.origin_system,
        origin_model=brief.origin_model,
        partner_system=brief.partner_system,
        partner_model=brief.partner_model,
        dossier=dossier,
    )
    disclosure = FoundationDisclosure(
        weakest_assumptions=[
            f"Growth assumption of {growth_pct}% holds across the horizon",
            f"Churn assumption of {churn_pct}% does not deteriorate",
            "Cost drivers scale linearly with revenue",
        ],
        invalidation_conditions=[
            "Growth slips by more than one planning cycle",
            "Churn rises 2 percentage points above plan",
        ],
        key_vulnerability=(
            "The forecast hinges on driver assumptions that look disciplined but "
            "are not yet evidenced by recent actuals."
        ),
    )
    score = _forecast_foundation_score(brief)
    attack = FoundationAttack(
        assumption_attacks=[
            "Growth may be optimistic relative to recent pipeline conversion.",
            "Churn may already be drifting upward in cohorts not yet in the model.",
            "Cost driver linearity ignores step-function hiring at scale.",
        ],
        invalidation_exploitation=[
            "If growth slips 1 cycle and churn rises, runway can break the floor.",
            "If hiring steps before revenue lands, opex compounds the miss.",
        ],
        vulnerability_strike=(
            "Forecast credibility depends on grounding driver assumptions in "
            "recent actuals — not policy aspiration."
        ),
        foundation_score=score,
        attack_summary=(
            "Forecast is directionally credible if the assumption registry is "
            "evidenced and stress views are explicit."
        ),
    )
    dossier.foundation_score = score
    return case, disclosure, attack


def _build_investment_case(
    brief: InvestmentBrief,
) -> Tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    decision_id = brief.decision_id or _decision_id("inv", brief.title)
    dossier = Dossier(
        core_problem=brief.problem,
        goal_state=[
            f"Payback <= {brief.expected_payback_months} months",
            f"Runway stays >= {brief.minimum_runway_months} months",
        ]
        + brief.expected_upside[:2],
        current_state=[
            f"Current runway: {brief.current_runway_months} months",
            f"Proposed investment: ${brief.investment_amount_usd:,.0f}",
        ],
        prior_decisions=[],
        constraints=[
            f"Do not reduce runway below {brief.minimum_runway_months} months",
            "Single accountable owner required",
        ]
        + brief.constraints,
        unknowns=[
            "Adoption and conversion timing",
            "Implementation execution capacity",
        ],
        scope=[
            "Foundation attack",
            "Spec lock",
            "Implementation QA",
        ],
        origin_direction=[
            "Prefer milestone-gated capital release",
            "Require explicit flip criteria before full commitment",
        ],
        structural_vulnerabilities=[
            "Revenue timing may lag implementation spend",
            "Strategic upside may be overstated relative to execution capacity",
        ],
    )
    case = DecisionCase(
        decision_id=decision_id,
        title=brief.title,
        domain=_domain_for(brief.task_type),
        created_at=_now(),
        owner=brief.owner,
        high_stakes=brief.high_stakes,
        origin_system=brief.origin_system,
        origin_model=brief.origin_model,
        partner_system=brief.partner_system,
        partner_model=brief.partner_model,
        dossier=dossier,
    )
    disclosure = FoundationDisclosure(
        weakest_assumptions=[
            f"Payback within {brief.expected_payback_months} months is achievable",
            "Strategic upside is material in this capital window",
            "Org can absorb implementation without harming core execution",
        ],
        invalidation_conditions=[
            f"Runway breaks {brief.minimum_runway_months}-month floor under downside",
            "Adoption slips by more than one planning cycle",
        ],
        key_vulnerability=(
            "The case depends on timing assumptions that look disciplined in "
            "theory but fail in operating reality."
        ),
    )
    score = _investment_foundation_score(brief)
    attack = FoundationAttack(
        assumption_attacks=[
            "Payback may rest on optimistic adoption rather than contracted demand.",
            "Strategic upside may be real but not near-term enough.",
            "Execution load may crowd out current priorities.",
        ],
        invalidation_exploitation=[
            "If spend lands before benefits, runway floor breaks fast.",
            "One-cycle adoption slip pushes economics outside hurdle tolerance.",
        ],
        vulnerability_strike=(
            "Most exposed where timing, not direction, carries the case."
        ),
        foundation_score=score,
        attack_summary=(
            "Directionally credible but timing-sensitive. Proceed only with "
            "milestone-gated release and explicit downside triggers."
        ),
    )
    dossier.foundation_score = score
    return case, disclosure, attack


def _build_board_case(
    brief: BoardBrief,
) -> Tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    decision_id = brief.decision_id or _decision_id("brd", brief.title)
    options = brief.options or ["Approve", "Defer", "Reject"]
    rec_idx = max(0, min(brief.recommended_option_index, len(options) - 1))
    dossier = Dossier(
        core_problem=brief.problem,
        goal_state=[
            "Board receives a single decision statement with explicit options",
            "Recommendation has flip criteria and a named owner",
        ]
        + brief.strategic_priorities[:2],
        current_state=[
            f"Options on the table: {len(options)}",
            f"Recommended: '{options[rec_idx]}'",
        ],
        prior_decisions=brief.prior_board_decisions,
        constraints=[
            "Decision must be lockable and replayable",
            "All open questions must be named, not buried",
        ]
        + brief.constraints,
        unknowns=brief.open_questions or [
            "Stakeholder alignment beyond exec",
            "Downstream policy implications",
        ],
        scope=[
            "Foundation attack on framing",
            "Spec lock on the decision",
            "Implementation ask + decision log",
        ],
        origin_direction=[
            "Prefer locking a clearly worded decision over hedged prose",
            "Surface dissent before vote, not after",
        ],
        structural_vulnerabilities=[
            "Framing may compress real disagreement",
            "Recommended option may dominate by inertia, not analysis",
        ],
    )
    case = DecisionCase(
        decision_id=decision_id,
        title=brief.title,
        domain=_domain_for(brief.task_type),
        created_at=_now(),
        owner=brief.owner,
        high_stakes=True,
        origin_system=brief.origin_system,
        origin_model=brief.origin_model,
        partner_system=brief.partner_system,
        partner_model=brief.partner_model,
        dossier=dossier,
    )
    disclosure = FoundationDisclosure(
        weakest_assumptions=[
            "The framing captures the actual decision the board needs to make",
            "The option set is exhaustive enough for a real choice",
            "Dissent will surface before the vote, not after",
        ],
        invalidation_conditions=[
            "A material option is missing from the slate",
            "Framing collapses two distinct decisions into one",
        ],
        key_vulnerability=(
            "Board decisions often fail on framing, not on the chosen option."
        ),
    )
    score = _board_foundation_score(brief, options)
    attack = FoundationAttack(
        assumption_attacks=[
            "Framing may have been optimized for consensus, not clarity.",
            "Option set may exclude a credible alternative the board would name.",
            "Dissent may exist but is unmeasured in the prep packet.",
        ],
        invalidation_exploitation=[
            "If framing is wrong, even a good vote locks the wrong decision.",
            "If dissent is unsurfaced, the lock is brittle and reopenable.",
        ],
        vulnerability_strike=(
            "Board hardening depends on naming, not deciding."
        ),
        foundation_score=score,
        attack_summary=(
            "Decision is lockable if framing survives adversarial review and "
            "the option slate is genuinely exhaustive."
        ),
    )
    dossier.foundation_score = score
    return case, disclosure, attack


def _forecast_foundation_score(brief: ForecastBrief) -> int:
    score = 78
    if brief.current_runway_months < brief.minimum_runway_months + 3:
        score -= 10
    if brief.growth_assumption_pct > 0.40:
        score -= 6
    if brief.churn_assumption_pct > 0.12:
        score -= 5
    if not brief.revenue_drivers:
        score -= 6
    return max(55, min(92, score))


def _investment_foundation_score(brief: InvestmentBrief) -> int:
    score = 78
    if brief.current_runway_months < brief.minimum_runway_months + 3:
        score -= 10
    if brief.expected_payback_months > 18:
        score -= 8
    if len(brief.key_risks) >= 4:
        score -= 4
    if brief.investment_amount_usd >= 5_000_000:
        score -= 3
    return max(55, min(92, score))


def _board_foundation_score(brief: BoardBrief, options: list[str]) -> int:
    score = 76
    if len(options) < 3:
        score -= 8
    if not brief.open_questions:
        score -= 4
    if not brief.strategic_risks:
        score -= 4
    if brief.recommended_option_index < 0 or brief.recommended_option_index >= len(options):
        score -= 6
    return max(55, min(92, score))


def _build_sweep_case(
    brief: SweepBrief,
) -> Tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    """Build decision case for an SEC filing sweep."""
    decision_id = brief.decision_id or _decision_id("sweep", brief.title)
    dossier = Dossier(
        core_problem=brief.problem,
        goal_state=[
            f"Sweep {len(brief.filing_types)} filing types for {brief.ticker or brief.company}",
            "Surface red flags: high 8-K count, S-1 amendments, activist PRE 14A, dilutive Form D",
            "Seed decision context for downstream brief",
        ]
        + brief.strategic_priorities[:2],
        current_state=[
            f"Ticker: {brief.ticker or 'N/A'}",
            f"CIK: {brief.cik or 'N/A'}",
            f"Filing types: {', '.join(brief.filing_types)}",
            f"Max filing age: {brief.min_filing_age_days} days",
        ],
        prior_decisions=[],
        constraints=[
            f"Filing data carries a {brief.min_filing_age_days}-day lag (SEC regulatory delay)",
            "Only publicly available EDGAR data",
        ]
        + brief.constraints,
        unknowns=[
            "Filing parsing quality depends on EDGAR format stability",
            "Non-standard attachments may not parse cleanly",
        ],
        scope=[
            "Filing sweep execution",
            "Red-flag heuristics",
            "Context seeding for downstream brief",
        ],
        origin_direction=[
            "Prefer filing sweep before deep-dive brief for full context",
            "Cross-reference 13F positions with latest 13D/G filings",
        ],
        structural_vulnerabilities=[
            "Sweep quality depends on filing completeness on EDGAR",
            "13F data may be stale if manager uses 45-day filing window",
            "S-1 amendments may be missed if filing system uses non-standard tags",
        ],
    )
    case = DecisionCase(
        decision_id=decision_id,
        title=brief.title,
        domain=_domain_for(brief.task_type),
        created_at=_now(),
        owner=brief.owner,
        high_stakes=brief.high_stakes,
        origin_system=brief.origin_system,
        origin_model=brief.origin_model,
        partner_system=brief.partner_system,
        partner_model=brief.partner_model,
        dossier=dossier,
    )
    disclosure = FoundationDisclosure(
        weakest_assumptions=[
            "EDGAR API is reachable and returns complete filing sets",
            "Filing text parsing handles modern XBRL iXBRL formats",
            "13F data is relevant despite regulatory filing lag",
        ],
        invalidation_conditions=[
            "EDGAR returns 503 or rate-limits the sweep",
            "Filing count is zero for primary types (10-K, 10-Q, 8-K)",
        ],
        key_vulnerability=(
            "Sweep value is highest when it catches something a brief would miss — "
            "a rapid 8-K cluster, an amended S-1, or activist PRE 14A."
        ),
    )
    score = _sweep_foundation_score(brief)
    attack = FoundationAttack(
        assumption_attacks=[
            "EDGAR may be rate-limiting or returning partial results for rapid-fire sweeps.",
            "XBRL parsing may miss narrative-only disclosures in 8-K exhibits.",
            "13F/13D cross-reference requires CUSIP→ticker mapping, which is incomplete.",
        ],
        invalidation_exploitation=[
            "If EDGAR returns partial results, red-flag heuristics may be silent on real risk.",
            "If CUSIP mapping is absent, manager positions remain opaque.",
        ],
        vulnerability_strike=(
            "Sweep is a decision-preparation tool, not a decision itself. "
            "The vulnerability is in trusting incomplete data as complete context."
        ),
        foundation_score=score,
        attack_summary=(
            "Filing sweep is directionally sound for pre-brief context seeding. "
            "Watch for EDGAR availability and filing completeness."
        ),
    )
    dossier.foundation_score = score
    return case, disclosure, attack


def _sweep_foundation_score(brief: SweepBrief) -> int:
    score = 80
    if not brief.ticker and not brief.cik:
        score -= 12
    if len(brief.filing_types) < 4:
        score -= 8
    if brief.min_filing_age_days > 90:
        score -= 6
    if not brief.carry_dossier_into_context:
        score -= 5
    return max(50, min(92, score))
