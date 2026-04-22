"""FinanceAgent — produces a financial view of the problem."""
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
    pb = Playbook(name="finance-playbook")
    pb.apply(
        [
            # Seeded via deltas so counters advance normally
        ]
    )
    # Seed some starter bullets directly
    starter = [
        (
            "strategies_and_hard_rules",
            "When sizing investment: separate fixed vs variable cost, then stress-test against 3 revenue scenarios before recommending.",
        ),
        (
            "verification_checklist",
            "Confirm the proposed spend has a named owner in the Entity map before sign-off.",
        ),
        (
            "troubleshooting_and_pitfalls",
            "A ROI estimate without a timeline is a vibe, not a number — always attach payback period.",
        ),
    ]
    for section, content in starter:
        pb.apply(
            [
                # Fake ADD
            ]
        )
        new_id = pb._next_id(section)
        pb.bullets[new_id] = Bullet(id=new_id, section=section, content=content, helpful=2)
    return pb


class FinanceAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="finance",
            capability=AgentCapability(
                domain="finance",
                produces=["budget_envelope", "roi_model"],
                consumes=[],
            ),
            playbook=_seed_playbook(),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        notes = context.get("relevant_notes", [])
        return [
            ExpansionStep(
                label="Reframe",
                content=(
                    f"Restated as a capital-allocation question: how much of the budget should be "
                    f"directed toward '{problem[:80]}' within this fiscal year?"
                ),
            ),
            ExpansionStep(
                label="Constraints",
                content=(
                    "Hard: annual OPEX ceiling, regulatory reserve requirements. "
                    "Soft: current quarter cash conversion cycle."
                ),
            ),
            ExpansionStep(
                label="Alternatives",
                content=(
                    "(A) Phased spend tied to milestone gates, (B) full upfront spend with claw-back "
                    "clauses, (C) co-funded with a partner to split exposure, (D) defer and run a "
                    "4-week discovery first."
                ),
                uncertainty_flags=["(C) assumes a partner willing to co-fund — unverified"],
            ),
            ExpansionStep(
                label="Assumptions",
                content=(
                    "Assume payback is measured in months, not quarters; assume the cost of capital "
                    "is ~8% unless the shared context says otherwise."
                ),
                uncertainty_flags=["cost-of-capital placeholder — confirm with Entity:finance_ops"],
            ),
            ExpansionStep(
                label="Edge cases",
                content=(
                    "If revenue forecast slips >15%, phased spend becomes mandatory. "
                    "If regulatory reserve tightens, options (A) and (C) survive; (B) does not."
                ),
            ),
            ExpansionStep(
                label="Cross-domain analogy",
                content=(
                    "Treat like staged venture-capital funding: each tranche unlocks only after the "
                    "previous milestone clears a defined success metric."
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
            "Recommend phased spend (Option A) with a 4-week discovery prepended: "
            "budget envelope of 60% of ask now, 40% gated on two go/no-go checkpoints. "
            "Payback target: 14 months at the central revenue scenario."
        )
        steps = [
            CompressionStep(
                label="Integrate",
                content=(
                    "Binding constraints are regulatory reserve and cash conversion cycle. "
                    "Options (B) and (C) are dominated once either tightens."
                ),
            ),
            CompressionStep(
                label="Commit",
                content="Phased + discovery dominates; shift risk to the org, keep optionality with the Board.",
            ),
        ]
        outputs = {
            "budget_envelope": "60% now / 40% gated",
            "roi_model": {"payback_months": 14, "scenarios": ["-15%", "central", "+20%"]},
        }
        return rec, steps, ConfidenceLevel.HIGH, (
            "Would change to full upfront (Option B) only if regulatory reserve eases AND "
            "the central revenue scenario holds for two consecutive quarters."
        ), outputs
