"""ComplianceAgent — validates the proposed plan against regulatory constraints."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from cme.agent import AgentCapability, MeshAgent
from cme.playbook import Bullet, Playbook
from cme.protocol import (
    CompressionStep,
    ConfidenceLevel,
    ExpansionStep,
)


def _seed_playbook() -> Playbook:
    pb = Playbook(name="compliance-playbook")
    starter = [
        (
            "strategies_and_hard_rules",
            "Any customer-data movement crossing a jurisdiction boundary requires a DPIA attached to the ticket.",
        ),
        (
            "verification_checklist",
            "Has an owner been named for incident response? (No name → block the launch.)",
        ),
        (
            "troubleshooting_and_pitfalls",
            "A 'low risk' label without a named mitigation is a red flag — demand the mitigation.",
        ),
    ]
    for section, content in starter:
        new_id = pb._next_id(section)
        pb.bullets[new_id] = Bullet(id=new_id, section=section, content=content, helpful=2)
    return pb


class ComplianceAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="compliance",
            capability=AgentCapability(
                domain="compliance",
                produces=["risk_register", "mitigations"],
                consumes=["market_positioning", "budget_envelope"],
            ),
            playbook=_seed_playbook(),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        upstream_hits = [
            n["content"]
            for n in context.get("relevant_notes", [])
            if n.get("source_agent") in {"finance", "strategy"}
        ]
        seed = upstream_hits[0] if upstream_hits else "(no upstream recommendation yet)"
        return [
            ExpansionStep(
                label="Reframe",
                content=(
                    "Recast the upstream plan as a set of data flows and decision points that must "
                    "each survive a regulator's question: 'who authorized this, and on what basis?'"
                ),
            ),
            ExpansionStep(
                label="Constraints",
                content=(
                    "Hard: data-residency rules, reserve requirements, customer-notice obligations. "
                    "Soft: audit turnaround time."
                ),
            ),
            ExpansionStep(
                label="Alternatives",
                content=(
                    "(α) Accept the plan, add DPIA + incident-response owner; "
                    "(β) Require scope reduction until residency questions resolve; "
                    "(γ) Pause and request Legal signoff."
                ),
            ),
            ExpansionStep(
                label="Assumptions",
                content=(
                    "Assume the upstream plan — "
                    + (seed[:160] + "…" if len(seed) > 160 else seed)
                    + " — is internally consistent; verify at grounding."
                ),
                uncertainty_flags=["upstream plan not yet cross-checked against Entity:regulators"],
            ),
            ExpansionStep(
                label="Edge cases",
                content=(
                    "If customer data crosses EU↔US, (α) is only valid with SCCs in place; "
                    "otherwise (β) or (γ) must apply."
                ),
            ),
            ExpansionStep(
                label="Cross-domain analogy",
                content=(
                    "Think like an FAA pre-flight checklist: any single unresolved item blocks the gate; "
                    "the checklist does not negotiate with the flight schedule."
                ),
            ),
        ]

    def compress(
        self,
        problem: str,
        expansion: List[ExpansionStep],
        context: Dict[str, Any],
    ) -> Tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        rec = (
            "Approve with conditions (Option α): attach DPIA + name an incident-response owner "
            "before any spend is released; require SCCs for any EU↔US data flow; schedule a "
            "30-day review checkpoint tied to the finance milestone gate."
        )
        steps = [
            CompressionStep(
                label="Integrate",
                content=(
                    "The finance phased-spend gate is a natural compliance checkpoint — reuse it "
                    "rather than creating a parallel control."
                ),
            ),
            CompressionStep(
                label="Commit",
                content="Conditional approval + gated review; escalate to Legal only if SCCs cannot be completed in 30 days.",
            ),
        ]
        outputs = {
            "risk_register": [
                {"risk": "cross-border data flow", "severity": "medium", "mitigation": "SCC"},
                {"risk": "incident response ownership", "severity": "high", "mitigation": "named owner"},
            ],
            "mitigations": ["DPIA", "SCC", "30-day checkpoint"],
        }
        return rec, steps, ConfidenceLevel.HIGH, (
            "Would escalate to (γ) pause-and-legal if cross-border flows involve special-category "
            "data OR the incident-response owner cannot be named within 10 business days."
        ), outputs
