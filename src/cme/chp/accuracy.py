"""Mandatory finance-analysis guard for CFO-grade CHP workflows."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from cme.chp.models import DecisionCase, SessionStatus
from cme.chp.runner import TriangulationResult, TriangulationRunner


@dataclass(frozen=True)
class CFOAccuracyPolicy:
    required_foundation_score: int = 100
    require_no_open_structural_vulnerabilities: bool = True
    require_no_open_blind_spots: bool = True

    def violations(self, case: DecisionCase) -> List[str]:
        issues: List[str] = []
        score = case.foundation_score or 0
        if score < self.required_foundation_score:
            issues.append(f"foundation score {score} is below CFO accuracy floor {self.required_foundation_score}")
        if self.require_no_open_structural_vulnerabilities and case.structural_vulnerabilities:
            issues.append("open structural vulnerabilities remain")
        if self.require_no_open_blind_spots and case.blind_spots:
            issues.append("open blind spots remain")
        return issues


@dataclass
class FinancialAnalysisGuardResult:
    policy: CFOAccuracyPolicy
    triangulation: TriangulationResult
    violations: List[str] = field(default_factory=list)

    @property
    def requires_human_verification(self) -> bool:
        return bool(self.violations)

    def render(self) -> str:
        lines = [
            "## CFO Accuracy Guard",
            f"- Status: {'REQUIRES_HUMAN_VERIFICATION' if self.requires_human_verification else 'CLEAR'}",
            f"- Accuracy Floor: {self.policy.required_foundation_score}",
        ]
        if self.violations:
            lines.append("- Blocking Violations:")
            lines.extend(f"  - {item}" for item in self.violations)
        lines.append(self.triangulation.render())
        return "\n".join(lines)


class FinancialAnalysisGuard:
    """Enforces mandatory CHP + adversary pass for finance analysis outputs."""

    def __init__(
        self,
        *,
        policy: CFOAccuracyPolicy | None = None,
        triangulation_runner: TriangulationRunner | None = None,
    ) -> None:
        self.policy = policy or CFOAccuracyPolicy()
        self.triangulation_runner = triangulation_runner or TriangulationRunner()

    def guard_case(self, case: DecisionCase, *, claim: str, context: str = "") -> FinancialAnalysisGuardResult:
        triangulation = self.triangulation_runner.run_adversary(
            claim,
            context=context,
            high_stakes=case.high_stakes,
        )
        violations = self.policy.violations(case)
        if triangulation.verification:
            violations.extend(triangulation.verification.failures())
        if triangulation.report.case.foundation_score and triangulation.report.case.foundation_score < self.policy.required_foundation_score:
            violations.append(
                f"adversary foundation score {triangulation.report.case.foundation_score} is below CFO accuracy floor {self.policy.required_foundation_score}"
            )
        case.blind_spots = list(dict.fromkeys(case.blind_spots + triangulation.adversary_findings))
        if violations and case.status == SessionStatus.LOCKED:
            case.status = SessionStatus.REQUIRES_HUMAN_VERIFICATION
        elif violations and case.status in {SessionStatus.PROVISIONAL, SessionStatus.PROVISIONAL_LOCK, SessionStatus.EXPLORING}:
            case.status = SessionStatus.REQUIRES_HUMAN_VERIFICATION
        return FinancialAnalysisGuardResult(
            policy=self.policy,
            triangulation=triangulation,
            violations=list(dict.fromkeys(violations)),
        )
