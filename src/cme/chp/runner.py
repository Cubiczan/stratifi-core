"""Triangulation runner for adversarial CHP passes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from cme.chp.contracts import CouncilSpawn, VerificationChecklist
from cme.chp.models import DecisionCase, Dossier, FoundationAttack, FoundationDisclosure, SessionStatus
from cme.chp.orchestrator import CHPOrchestrator, CHPReport


@dataclass
class TriangulationResult:
    claim: str
    report: CHPReport
    adversary_findings: List[str] = field(default_factory=list)
    council_spawn: CouncilSpawn | None = None
    verification: VerificationChecklist | None = None

    @property
    def status(self) -> SessionStatus:
        return self.report.case.status

    def render(self) -> str:
        lines = [
            "## TriangulationRunner Adversary Pass",
            f"- Claim: {self.claim}",
            f"- Status: {self.status.value}",
            f"- Foundation Score: {self.report.case.foundation_score}",
        ]
        if self.adversary_findings:
            lines.append("- Findings:")
            lines.extend(f"  - {item}" for item in self.adversary_findings)
        if self.council_spawn:
            lines.append(f"- Council Spawn: {self.council_spawn.trigger_reason}")
        if self.verification:
            failures = self.verification.failures()
            lines.append(f"- Verification Failures: {len(failures)}")
            lines.extend(f"  - {item}" for item in failures[:6])
        return "\n".join(lines)


class TriangulationRunner:
    """Runs a one-shot CHP adversary/fact-check pass around a claim."""

    def __init__(self, *, orchestrator: CHPOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or CHPOrchestrator()

    @classmethod
    def as_adversary(cls, claim: str, *, context: str = "", high_stakes: bool = True) -> TriangulationResult:
        return cls().run_adversary(claim, context=context, high_stakes=high_stakes)

    def run_adversary(self, claim: str, *, context: str = "", high_stakes: bool = True) -> TriangulationResult:
        case, disclosure, attack = self._build_case(claim, context=context, high_stakes=high_stakes)
        report = self.orchestrator.run_initial_session(
            case=case,
            foundation_disclosure=disclosure,
            foundation_attack=attack,
        )
        confidence = report.case.foundation_score or 0
        council = CouncilSpawn.maybe_spawn(
            high_stakes=high_stakes,
            confidence_pct=confidence,
            current_round=report.case.current_round,
        )
        verification = VerificationChecklist.run(report.case, packet=report.initial_packet)
        findings = self._findings(claim, context=context)
        return TriangulationResult(
            claim=claim,
            report=report,
            adversary_findings=findings,
            council_spawn=council,
            verification=verification,
        )

    def _build_case(
        self,
        claim: str,
        *,
        context: str,
        high_stakes: bool,
    ) -> tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
        score = self._foundation_score(claim, context)
        dossier = Dossier(
            core_problem=f"Fact-check and adversarially validate this finance claim: {claim}",
            goal_state=[
                "No unsupported numeric claim advances without human-readable evidence",
                "All open assumptions, blind spots, and structural vulnerabilities are explicit",
                "Decision output remains blocked unless finance accuracy policy is satisfied",
            ],
            current_state=[
                f"Claim under review: {claim}",
                f"Context length: {len(context)} characters",
                f"Initial adversary foundation score: {score}",
            ],
            constraints=[
                "CFO workflows require human-verifiable accuracy",
                "No final lock if a vulnerability or blind spot remains open",
                "All analysis must survive adversarial foundation attack",
            ],
            unknowns=[
                "Whether all numbers are tied to auditable source data",
                "Whether the recommendation depends on untested assumptions",
            ],
            scope=[
                "Foundation attack",
                "Spec validation",
                "Human verification gate",
            ],
            origin_direction=[
                "Assume the claim is incomplete until evidence proves otherwise",
                "Prioritize falsification over agreement",
                "Block lock progression when finance evidence is incomplete",
            ],
            structural_vulnerabilities=[
                "Financial analysis can look precise while source evidence is incomplete",
                "A model can converge around a narrative before the math is fully verified",
            ],
        )
        case = DecisionCase(
            decision_id=f"triangulation-{abs(hash(claim)) % 10_000_000}",
            title="TriangulationRunner adversary pass",
            domain="finance_adversary",
            created_at=datetime.now(timezone.utc).isoformat(),
            owner="cfo",
            high_stakes=high_stakes,
            origin_system="CHP",
            origin_model="adversary-runner",
            partner_system="Partner",
            partner_model="fact-check-agent",
            dossier=dossier,
        )
        disclosure = FoundationDisclosure(
            weakest_assumptions=[
                "The claim is numerically accurate and source-grounded",
                "The recommendation does not hide material uncertainty",
                "The analysis can be trusted without additional human verification",
            ],
            invalidation_conditions=[
                "Any key number lacks source evidence or reproducible calculation",
                "Any open blind spot or structural vulnerability remains unresolved",
            ],
            key_vulnerability="The claim can sound CFO-ready before it is actually audit-ready.",
        )
        attack = FoundationAttack(
            assumption_attacks=[
                "Numeric precision is not the same as verified accuracy.",
                "A confident recommendation may compress unresolved assumptions.",
                "Finance decisions can fail when source data, timing, or definitions are inconsistent.",
            ],
            invalidation_exploitation=[
                "One unsupported KPI or forecast input can invalidate the downstream recommendation.",
                "One unresolved blind spot can block lock progression under the CFO accuracy policy.",
            ],
            vulnerability_strike="This analysis must remain blocked unless every material number and assumption is human-verifiable.",
            foundation_score=score,
            attack_summary="The adversary pass treats the claim as untrusted until evidence, assumptions, and vulnerabilities are fully resolved.",
        )
        dossier.foundation_score = score
        return case, disclosure, attack

    @staticmethod
    def _foundation_score(claim: str, context: str) -> int:
        score = 82
        lowered = f"{claim} {context}".lower()
        if any(token in lowered for token in ("estimated", "assume", "rough", "directional", "approx")):
            score -= 10
        if any(char.isdigit() for char in claim) and not any(token in lowered for token in ("source", "csv", "xlsx", "ledger", "actual", "budget")):
            score -= 8
        if "100%" not in lowered and "verified" not in lowered:
            score -= 5
        return max(50, min(95, score))

    @staticmethod
    def _findings(claim: str, *, context: str) -> List[str]:
        findings = [
            "Treat every financial number as unverified until tied to source data.",
            "Require explicit flip criteria for any provisional recommendation.",
        ]
        if any(char.isdigit() for char in claim) and "source" not in context.lower():
            findings.append("The claim includes a number but no explicit source reference in context.")
        return findings
