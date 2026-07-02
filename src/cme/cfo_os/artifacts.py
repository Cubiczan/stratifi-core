"""CFO-grade artifact templates produced by a CFO OS session.

A single multi-agent run lands one of three artifact shapes:

    - ForecastPack       (driver-level forecast with stress views and lock state)
    - InvestmentCaseMemo (capital allocation memo with ROI + risks + flip criteria)
    - BoardOutput        (decision packet for the board with options + dissent)

All artifacts share the ``CFOArtifact`` interface: ``render() -> str`` markdown,
plus structural fields the audit trail can index.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from cme.agent import TurnResult
from cme.chp.models import DecisionCase, SessionStatus
from cme.cfo_os.briefs import BoardBrief, ForecastBrief, InvestmentBrief, SweepBrief


@dataclass
class CFOArtifact:
    title: str
    decision_id: str
    lock_state: str
    sections: List[Dict[str, Any]] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"# {self.title}",
            f"_decision_id: `{self.decision_id}`  ·  lock_state: **{self.lock_state}**_",
            "",
        ]
        for s in self.sections:
            lines.append(f"## {s['heading']}")
            for item in s.get("bullets", []):
                lines.append(f"- {item}")
            if s.get("body"):
                lines.append("")
                lines.append(s["body"])
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


@dataclass
class ForecastPack(CFOArtifact):
    pass


@dataclass
class InvestmentCaseMemo(CFOArtifact):
    pass


@dataclass
class BoardOutput(CFOArtifact):
    pass


@dataclass
class SweepPack(CFOArtifact):
    """SEC filing sweep output — regulatory context for downstream briefs."""

    pass


# --- Builders ---------------------------------------------------------------


def _by_agent(turns: List[TurnResult]) -> Dict[str, TurnResult]:
    return {t.agent: t for t in turns}


def _lock_state(case: DecisionCase) -> str:
    return case.status.value if isinstance(case.status, SessionStatus) else str(case.status)


def build_forecast_pack(
    *,
    brief: ForecastBrief,
    case: DecisionCase,
    turns: List[TurnResult],
) -> ForecastPack:
    by_agent = _by_agent(turns)
    finance = by_agent.get("finance")
    strategy = by_agent.get("strategy")
    compliance = by_agent.get("compliance")

    drivers_section = {
        "heading": "Driver Registry",
        "bullets": [f"Revenue driver: {d}" for d in brief.revenue_drivers]
        + [f"Cost driver: {d}" for d in brief.cost_drivers],
    }
    base_section = {
        "heading": "Baseline Inputs",
        "bullets": [
            f"Base revenue: ${brief.base_revenue_usd:,.0f}",
            f"Base opex: ${brief.base_opex_usd:,.0f}",
            f"Growth assumption: {brief.growth_assumption_pct * 100:.1f}%",
            f"Churn assumption: {brief.churn_assumption_pct * 100:.1f}%",
            f"Current runway: {brief.current_runway_months} months "
            f"(floor: {brief.minimum_runway_months})",
        ],
    }
    finance_view = {
        "heading": "Finance View",
        "bullets": _agent_bullets(finance),
    }
    strategy_view = {
        "heading": "Strategy View",
        "bullets": _agent_bullets(strategy),
    }
    compliance_view = {
        "heading": "Compliance View",
        "bullets": _agent_bullets(compliance),
    }
    stress_section = {
        "heading": "Stress Views",
        "bullets": [
            f"Downside: growth -{int(brief.growth_assumption_pct * 100 / 2)}%, "
            f"churn +200bps -> tests runway floor",
            "Central: as-stated assumptions hold across the horizon",
            f"Upside: growth +{int(brief.growth_assumption_pct * 100 / 2)}%, churn flat -> "
            "tests cost-driver step functions",
        ],
    }
    lock_section = {
        "heading": "Plan Lock Status",
        "bullets": [
            f"Foundation score: {case.foundation_score}",
            f"Status: {_lock_state(case)}",
            "Locked items advance only after third-party validation (CHP).",
        ],
    }

    return ForecastPack(
        title=f"Forecast Pack — {brief.title}",
        decision_id=case.decision_id,
        lock_state=_lock_state(case),
        sections=[
            base_section,
            drivers_section,
            finance_view,
            strategy_view,
            compliance_view,
            stress_section,
            lock_section,
        ],
    )


def build_investment_case_memo(
    *,
    brief: InvestmentBrief,
    case: DecisionCase,
    turns: List[TurnResult],
) -> InvestmentCaseMemo:
    by_agent = _by_agent(turns)
    finance = by_agent.get("finance")
    strategy = by_agent.get("strategy")
    compliance = by_agent.get("compliance")

    inputs_section = {
        "heading": "Investment Inputs",
        "bullets": [
            f"Amount: ${brief.investment_amount_usd:,.0f}",
            f"Expected payback: {brief.expected_payback_months} months",
            f"Current runway: {brief.current_runway_months} months "
            f"(floor: {brief.minimum_runway_months})",
        ],
    }
    upside_section = {
        "heading": "Strategic Upside",
        "bullets": brief.expected_upside or ["(none stated)"],
    }
    risks_section = {
        "heading": "Key Risks",
        "bullets": brief.key_risks or ["(none stated)"],
    }
    finance_view = {
        "heading": "Finance Recommendation",
        "bullets": _agent_bullets(finance),
    }
    strategy_view = {
        "heading": "Strategy Positioning",
        "bullets": _agent_bullets(strategy),
    }
    compliance_view = {
        "heading": "Compliance Conditions",
        "bullets": _agent_bullets(compliance),
    }
    flip_section = {
        "heading": "Flip Criteria",
        "bullets": _flip_criteria(turns)
        or [
            "Runway breaks the floor under downside",
            "Adoption slips by more than one planning cycle",
        ],
    }
    lock_section = {
        "heading": "Lock Status",
        "bullets": [
            f"Foundation score: {case.foundation_score}",
            f"Status: {_lock_state(case)}",
            "Capital release is gated on milestone-by-milestone confirmation.",
        ],
    }

    return InvestmentCaseMemo(
        title=f"Investment Case Memo — {brief.title}",
        decision_id=case.decision_id,
        lock_state=_lock_state(case),
        sections=[
            inputs_section,
            upside_section,
            risks_section,
            finance_view,
            strategy_view,
            compliance_view,
            flip_section,
            lock_section,
        ],
    )


def build_sweep_pack(
    *,
    brief: SweepBrief,
    case: DecisionCase,
    turns: List[TurnResult],
) -> SweepPack:
    """Build a SweepPack from a SweepBrief + CHP case + agent turns."""
    by_agent = _by_agent(turns)
    finance = by_agent.get("finance")
    strategy = by_agent.get("strategy")
    compliance = by_agent.get("compliance")

    target_section = {
        "heading": "Sweep Target",
        "bullets": [
            f"Company: {brief.company}",
            f"Ticker: {brief.ticker or 'N/A'}",
            f"CIK: {brief.cik or 'auto-resolve'}",
            f"Filing types: {', '.join(brief.filing_types)}",
            f"Age filter: {brief.min_filing_age_days} days",
        ],
    }
    finance_view = {
        "heading": "Finance View",
        "bullets": _agent_bullets(finance),
    }
    strategy_view = {
        "heading": "Strategy View",
        "bullets": _agent_bullets(strategy),
    }
    compliance_view = {
        "heading": "Compliance View",
        "bullets": _agent_bullets(compliance),
    }
    context_section = {
        "heading": "Context Seeding",
        "bullets": [
            "Sweep data seeded into ContextEngine for downstream brief",
            f"Carry dossier: {'yes' if brief.carry_dossier_into_context else 'no'}",
        ],
    }
    lock_section = {
        "heading": "Sweep Lock Status",
        "bullets": [
            f"Foundation score: {case.foundation_score}",
            f"Status: {_lock_state(case)}",
            "Sweep is a pre-brief artifact — downstream decisions carry separate CHP sessions.",
        ],
    }

    return SweepPack(
        title=f"SEC Filing Sweep — {brief.ticker or brief.company}",
        decision_id=case.decision_id,
        lock_state=_lock_state(case),
        sections=[
            target_section,
            finance_view,
            strategy_view,
            compliance_view,
            context_section,
            lock_section,
        ],
    )


def build_board_output(
    *,
    brief: BoardBrief,
    case: DecisionCase,
    turns: List[TurnResult],
) -> BoardOutput:
    by_agent = _by_agent(turns)
    finance = by_agent.get("finance")
    strategy = by_agent.get("strategy")
    compliance = by_agent.get("compliance")

    options = brief.options or ["Approve", "Defer", "Reject"]
    rec_idx = max(0, min(brief.recommended_option_index, len(options) - 1))

    decision_section = {
        "heading": "Decision Statement",
        "bullets": [brief.problem],
    }
    options_section = {
        "heading": "Options",
        "bullets": [
            f"{'(recommended) ' if i == rec_idx else ''}{i + 1}. {opt}"
            for i, opt in enumerate(options)
        ],
    }
    open_q_section = {
        "heading": "Open Questions",
        "bullets": brief.open_questions or ["(none surfaced)"],
    }
    risks_section = {
        "heading": "Strategic Risks",
        "bullets": brief.strategic_risks or ["(none stated)"],
    }
    finance_view = {
        "heading": "Finance Read",
        "bullets": _agent_bullets(finance),
    }
    strategy_view = {
        "heading": "Strategy Read",
        "bullets": _agent_bullets(strategy),
    }
    compliance_view = {
        "heading": "Compliance Read",
        "bullets": _agent_bullets(compliance),
    }
    lock_section = {
        "heading": "Lock + Replay",
        "bullets": [
            f"Foundation score: {case.foundation_score}",
            f"Status: {_lock_state(case)}",
            "Decision lock progresses only after validator confirmation (CHP).",
            "Vote, dissent, and flip criteria are recorded in the registry.",
        ],
    }

    return BoardOutput(
        title=f"Board Output — {brief.title}",
        decision_id=case.decision_id,
        lock_state=_lock_state(case),
        sections=[
            decision_section,
            options_section,
            open_q_section,
            risks_section,
            finance_view,
            strategy_view,
            compliance_view,
            lock_section,
        ],
    )


def _agent_bullets(turn: TurnResult | None) -> List[str]:
    if not turn:
        return ["(agent did not run)"]
    bullets: List[str] = [f"Recommendation: {turn.trace.recommendation}"]
    if turn.trace.what_would_change:
        bullets.append(f"Would change if: {turn.trace.what_would_change}")
    bullets.append(f"Confidence: {turn.trace.confidence.value}")
    if turn.deltas_applied:
        bullets.append(f"Playbook deltas: {len(turn.deltas_applied)}")
    return bullets


def _flip_criteria(turns: List[TurnResult]) -> List[str]:
    criteria: List[str] = []
    for t in turns:
        if t.trace.what_would_change:
            criteria.append(f"{t.agent}: {t.trace.what_would_change}")
    return criteria
