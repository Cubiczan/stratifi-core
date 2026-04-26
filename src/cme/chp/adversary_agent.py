"""MeshAgent wrapper that runs a CHP adversary pass."""
from __future__ import annotations

from typing import Any, Dict, List

from cme.agent import AgentCapability, MeshAgent
from cme.chp.runner import TriangulationRunner
from cme.protocol import CompressionStep, ConfidenceLevel, ExpansionStep


class AdversaryMeshAgent(MeshAgent):
    """Drop-in mesh agent for fact-checking finance recommendations."""

    def __init__(self, *, runner: TriangulationRunner | None = None) -> None:
        super().__init__(
            name="chp_adversary",
            capability=AgentCapability(
                domain="finance_adversary",
                produces=["adversary_findings", "verification_gate"],
                consumes=["recommendation", "financial_analysis"],
            ),
        )
        self.runner = runner or TriangulationRunner()

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        result = self.runner.run_adversary(problem, context=str(context), high_stakes=True)
        findings = result.adversary_findings or ["No adversary findings generated."]
        return [
            ExpansionStep(label="Foundation Attack", content=result.report.foundation_attack.attack_summary),
            ExpansionStep(label="Accuracy Gate", content=result.render()),
            ExpansionStep(label="Findings", content=" | ".join(findings)),
        ]

    def compress(
        self,
        problem: str,
        expansion: List[ExpansionStep],
        context: Dict[str, Any],
    ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        result = self.runner.run_adversary(problem, context=str(context), high_stakes=True)
        recommendation = (
            "Require human verification before lock."
            if result.report.case.foundation_score != 100
            else "Adversary pass clear."
        )
        return (
            recommendation,
            [CompressionStep(label="Adversary Decision", content=result.render())],
            ConfidenceLevel.HIGH if result.report.case.foundation_score == 100 else ConfidenceLevel.LOW,
            "Would change only if all financial claims are source-verified and no vulnerabilities remain.",
            {
                "adversary_findings": result.adversary_findings,
                "verification_gate": result.status.value,
            },
        )
