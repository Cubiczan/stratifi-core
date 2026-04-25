"""Investment committee scoring workflow with CHP hardening."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from cme.chp.models import DecisionCase, Dossier, FoundationAttack, FoundationDisclosure


WEIGHTS = {
    "strategic_fit": 0.25,
    "returns": 0.25,
    "unit_economics": 0.15,
    "evidence_quality": 0.15,
    "execution_risk": 0.20,
}


@dataclass
class InvestmentProposal:
    title: str
    company: str
    proposal_type: str
    investment_amount_usd: float
    annual_revenue_uplift_usd: float = 0.0
    annual_cost_savings_usd: float = 0.0
    npv_usd: float = 0.0
    irr_pct: float = 0.0
    payback_months: float = 0.0
    cac_usd: float = 0.0
    ltv_usd: float = 0.0
    gross_margin_pct: float = 0.0
    strategic_fit_score: float = 7.0
    evidence_quality_score: float = 6.0
    execution_risk_score: float = 5.0
    market_confidence_score: float = 6.0
    sponsor: str = "CFO"
    strategic_rationale: List[str] = field(default_factory=list)
    key_risks: List[str] = field(default_factory=list)
    evidence_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CriterionScore:
    name: str
    score: float
    weight: float
    weighted_score: float
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InvestmentCommitteeResult:
    proposal: InvestmentProposal
    scorecard: List[CriterionScore]
    total_score: float
    recommendation: str
    evidence_gaps: List[str]
    sensitivities: Dict[str, float]
    committee_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal": self.proposal.to_dict(),
            "scorecard": [item.to_dict() for item in self.scorecard],
            "total_score": self.total_score,
            "recommendation": self.recommendation,
            "evidence_gaps": self.evidence_gaps,
            "sensitivities": self.sensitivities,
            "committee_notes": self.committee_notes,
        }


def load_investment_proposal(path: str | Path) -> InvestmentProposal:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return InvestmentProposal(
        title=payload["title"],
        company=payload["company"],
        proposal_type=payload.get("proposal_type", "growth_bet"),
        investment_amount_usd=float(payload["investment_amount_usd"]),
        annual_revenue_uplift_usd=float(payload.get("annual_revenue_uplift_usd", 0.0)),
        annual_cost_savings_usd=float(payload.get("annual_cost_savings_usd", 0.0)),
        npv_usd=float(payload.get("npv_usd", 0.0)),
        irr_pct=float(payload.get("irr_pct", 0.0)),
        payback_months=float(payload.get("payback_months", 0.0)),
        cac_usd=float(payload.get("cac_usd", 0.0)),
        ltv_usd=float(payload.get("ltv_usd", 0.0)),
        gross_margin_pct=float(payload.get("gross_margin_pct", 0.0)),
        strategic_fit_score=float(payload.get("strategic_fit_score", 7.0)),
        evidence_quality_score=float(payload.get("evidence_quality_score", 6.0)),
        execution_risk_score=float(payload.get("execution_risk_score", 5.0)),
        market_confidence_score=float(payload.get("market_confidence_score", 6.0)),
        sponsor=payload.get("sponsor", "CFO"),
        strategic_rationale=list(payload.get("strategic_rationale", [])),
        key_risks=list(payload.get("key_risks", [])),
        evidence_items=list(payload.get("evidence_items", [])),
    )


def score_investment_proposal(proposal: InvestmentProposal) -> InvestmentCommitteeResult:
    annual_value = proposal.annual_revenue_uplift_usd + proposal.annual_cost_savings_usd
    returns_score = _returns_score(proposal, annual_value)
    unit_economics_score = _unit_economics_score(proposal)
    execution_score = max(0.0, min(10.0, 10.0 - proposal.execution_risk_score + (proposal.market_confidence_score - 5.0) * 0.3))
    scorecard = [
        CriterionScore(
            name="Strategic Fit",
            score=proposal.strategic_fit_score,
            weight=WEIGHTS["strategic_fit"],
            weighted_score=proposal.strategic_fit_score * WEIGHTS["strategic_fit"],
            rationale="Based on sponsor input and alignment with stated strategic rationale.",
        ),
        CriterionScore(
            name="Returns",
            score=returns_score,
            weight=WEIGHTS["returns"],
            weighted_score=returns_score * WEIGHTS["returns"],
            rationale="Combines payback, IRR, NPV, and annual value creation signal.",
        ),
        CriterionScore(
            name="Unit Economics",
            score=unit_economics_score,
            weight=WEIGHTS["unit_economics"],
            weighted_score=unit_economics_score * WEIGHTS["unit_economics"],
            rationale="Uses LTV/CAC and gross margin to test quality of growth or capital efficiency.",
        ),
        CriterionScore(
            name="Evidence Quality",
            score=proposal.evidence_quality_score,
            weight=WEIGHTS["evidence_quality"],
            weighted_score=proposal.evidence_quality_score * WEIGHTS["evidence_quality"],
            rationale="Rates how well the proposal is grounded in data, diligence, and external validation.",
        ),
        CriterionScore(
            name="Execution Risk",
            score=execution_score,
            weight=WEIGHTS["execution_risk"],
            weighted_score=execution_score * WEIGHTS["execution_risk"],
            rationale="Rewards simpler execution and penalizes high delivery risk or uncertain adoption.",
        ),
    ]
    total_score = round(sum(item.weighted_score for item in scorecard), 2)
    recommendation = _recommendation(total_score)
    evidence_gaps = _evidence_gaps(proposal)
    sensitivities = {
        "ltv_cac_ratio": round(proposal.ltv_usd / proposal.cac_usd, 2) if proposal.cac_usd else 0.0,
        "annual_value_vs_investment": round(annual_value / proposal.investment_amount_usd, 2)
        if proposal.investment_amount_usd
        else 0.0,
        "downside_case_score": round(max(0.0, total_score - 1.1), 2),
        "upside_case_score": round(min(10.0, total_score + 0.8), 2),
    }
    committee_notes = _committee_notes(proposal, total_score, recommendation, sensitivities)
    return InvestmentCommitteeResult(
        proposal=proposal,
        scorecard=scorecard,
        total_score=total_score,
        recommendation=recommendation,
        evidence_gaps=evidence_gaps,
        sensitivities=sensitivities,
        committee_notes=committee_notes,
    )


def build_investment_committee_case(
    result: InvestmentCommitteeResult,
    *,
    owner: str = "cfo",
    origin_system: str = "Claude",
    origin_model: str = "GPT-5.4",
    partner_system: str = "Partner",
    partner_model: str = "GPT-5-equivalent",
) -> tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    proposal = result.proposal
    dossier = Dossier(
        core_problem=f"Determine whether {proposal.title} should advance through the investment committee based on returns, evidence quality, and execution risk.",
        goal_state=[
            "Score the proposal consistently across return, strategic fit, and delivery risk",
            "Surface evidence gaps before a committee recommendation is treated as final",
            "Translate DCF and CAC/LTV style inputs into one committee-ready decision packet",
        ],
        current_state=[
            f"Total score is {result.total_score:.2f} / 10",
            f"Recommendation is {result.recommendation}",
            f"Investment amount is ${proposal.investment_amount_usd:,.0f}",
            f"Payback is {proposal.payback_months:.1f} months",
        ],
        prior_decisions=[],
        constraints=[
            "The scorecard is a committee filter rather than a full diligence memo",
            "Return metrics may be based on directional assumptions rather than finalized models",
            "The tool must work across capex, software, acquisition, and growth proposals",
        ],
        unknowns=[
            "Evidence quality can lag behind the apparent precision of return estimates",
            "Execution risk may be understated by proposal sponsors",
        ],
        scope=[
            "Scorecard weighting",
            "Evidence gap analysis",
            "Sensitivity framing",
            "Recommendation tiering",
        ],
        origin_direction=[
            "Prefer disciplined capital allocation over optimistic storytelling",
            "Penalize weak evidence even when the modeled upside looks attractive",
        ],
        structural_vulnerabilities=[
            "A weighted score can hide one fatal flaw inside an otherwise attractive proposal",
            "The tool can inherit optimism bias if sponsors overstate strategic fit or evidence quality",
        ],
    )
    case = DecisionCase(
        decision_id=f"investment-committee-{proposal.title.lower().replace(' ', '-')}",
        title=f"Investment committee review: {proposal.title}",
        domain="investment_committee",
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
            "The scorecard weights reflect how this committee really allocates capital",
            "Return metrics are directionally credible enough to inform gating decisions",
            "Sponsor-supplied strategic fit and evidence scores are not overstated",
        ],
        invalidation_conditions=[
            "The proposal hides critical diligence gaps or risk concentrations outside the scorecard",
            "A single untested assumption drives most of the modeled upside",
        ],
        key_vulnerability="The model is most exposed where committee scoring turns uncertain assumptions into false precision.",
    )
    score = 84
    if result.total_score < 6.5:
        score -= 10
    score -= min(10, len(result.evidence_gaps) * 2)
    if proposal.payback_months and proposal.payback_months > 30:
        score -= 6
    attack = FoundationAttack(
        assumption_attacks=[
            "Weighted scoring can mask a single non-negotiable failure, especially around evidence quality or integration risk.",
            "DCF and CAC/LTV style inputs often look more reliable than the underlying assumptions deserve.",
            "Sponsor-supplied strategic fit can inflate scores if the committee does not calibrate independently.",
        ],
        invalidation_exploitation=[
            "If one core assumption around payback, adoption, or value capture fails, the recommendation tier can change materially.",
            "Weak diligence can make a strong numeric score look defendable when it is actually fragile.",
        ],
        vulnerability_strike="The scorecard helps only if it is used to expose uncertainty rather than compress it into a comfortable number.",
        foundation_score=max(58, min(91, score)),
        attack_summary="The tool is strong for disciplined screening, but it must treat evidence gaps and execution risk as first-class blockers rather than side notes.",
    )
    dossier.foundation_score = attack.foundation_score
    dossier.prior_round_summary = [f"Recommendation tier: {result.recommendation}"]
    return case, disclosure, attack


def render_investment_committee_markdown(result: InvestmentCommitteeResult) -> str:
    proposal = result.proposal
    lines = [
        "# Investment Committee Scoring Tool",
        f"**Proposal:** {proposal.title}",
        f"**Company:** {proposal.company}",
        f"**Recommendation:** {result.recommendation}",
        f"**Total Score:** {result.total_score:.2f} / 10",
        "",
        "## Scorecard",
    ]
    for item in result.scorecard:
        lines.append(
            f"- {item.name}: {item.score:.1f}/10 | weight={item.weight:.0%} | weighted={item.weighted_score:.2f}"
        )
    lines.extend(["", "## Evidence Gaps"])
    for item in result.evidence_gaps or ["None identified"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Committee Notes"])
    for item in result.committee_notes:
        lines.append(f"- {item}")
    return "\n".join(lines)


def export_investment_committee_workbook(
    result: InvestmentCommitteeResult,
    *,
    session_summary: str,
    output_path: str | Path,
) -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    builder_path = repo_root / "tools" / "build_investment_committee_workbook.mjs"
    node_path = _resolve_node_path()
    _ensure_node_modules_link(repo_root)
    payload = {"committee": result.to_dict(), "session_summary": session_summary}
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


def _returns_score(proposal: InvestmentProposal, annual_value: float) -> float:
    score = 4.0
    if proposal.payback_months:
        if proposal.payback_months <= 12:
            score += 3.0
        elif proposal.payback_months <= 24:
            score += 2.0
        elif proposal.payback_months <= 36:
            score += 1.0
    if proposal.irr_pct >= 0.25:
        score += 1.8
    elif proposal.irr_pct >= 0.15:
        score += 1.1
    if proposal.npv_usd > 0:
        score += 0.8
    if proposal.investment_amount_usd and annual_value / proposal.investment_amount_usd >= 0.5:
        score += 0.8
    return round(max(0.0, min(10.0, score)), 1)


def _unit_economics_score(proposal: InvestmentProposal) -> float:
    score = 5.0
    if proposal.cac_usd and proposal.ltv_usd:
        ratio = proposal.ltv_usd / proposal.cac_usd
        if ratio >= 5:
            score += 3.0
        elif ratio >= 3:
            score += 2.0
        elif ratio >= 2:
            score += 1.0
        else:
            score -= 1.5
    if proposal.gross_margin_pct >= 0.75:
        score += 1.0
    elif proposal.gross_margin_pct < 0.5:
        score -= 1.0
    return round(max(0.0, min(10.0, score)), 1)


def _recommendation(total_score: float) -> str:
    if total_score >= 8.0:
        return "Advance"
    if total_score >= 6.5:
        return "Advance with Conditions"
    if total_score >= 5.0:
        return "Hold"
    return "Do Not Advance"


def _evidence_gaps(proposal: InvestmentProposal) -> List[str]:
    gaps: List[str] = []
    if len(proposal.evidence_items) < 3:
        gaps.append("Evidence pack is thin relative to the size of the proposal.")
    if proposal.npv_usd == 0 and proposal.irr_pct == 0:
        gaps.append("Return case lacks a clear NPV or IRR anchor.")
    if proposal.cac_usd == 0 or proposal.ltv_usd == 0:
        gaps.append("Unit economics are incomplete, so the committee cannot fully test efficiency assumptions.")
    if not proposal.key_risks:
        gaps.append("No explicit risk register is attached to the proposal.")
    return gaps


def _committee_notes(
    proposal: InvestmentProposal,
    total_score: float,
    recommendation: str,
    sensitivities: Dict[str, float],
) -> List[str]:
    notes = [
        f"Recommendation is {recommendation} at {total_score:.2f} / 10.",
        f"Modeled payback is {proposal.payback_months:.1f} months on an investment of ${proposal.investment_amount_usd:,.0f}.",
    ]
    if sensitivities["ltv_cac_ratio"]:
        notes.append(f"LTV/CAC is {sensitivities['ltv_cac_ratio']:.2f}x, which sets the quality bar for customer-driven upside.")
    notes.append(
        f"Downside and upside score range is {sensitivities['downside_case_score']:.2f} to {sensitivities['upside_case_score']:.2f}."
    )
    return notes


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
