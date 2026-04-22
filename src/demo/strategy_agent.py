"""StrategyAgent — produces competitive/positioning view of the problem."""
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
    pb = Playbook(name="strategy-playbook")
    starter = [
        (
            "strategies_and_hard_rules",
            "Every strategy recommendation names the competitor or market motion that would falsify it.",
        ),
        (
            "domain_concepts",
            "Where-to-Play × How-to-Win: a choice on one axis without the other is an aspiration, not a strategy.",
        ),
        (
            "verification_checklist",
            "Does the recommendation survive the 'competitor mirrors us next quarter' test?",
        ),
    ]
    for section, content in starter:
        new_id = pb._next_id(section)
        pb.bullets[new_id] = Bullet(id=new_id, section=section, content=content, helpful=2)
    return pb


class StrategyAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="strategy",
            capability=AgentCapability(
                domain="strategy",
                produces=["market_positioning", "go_to_market"],
                consumes=["budget_envelope"],
            ),
            playbook=_seed_playbook(),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        budget_note = ""
        for n in context.get("relevant_notes", []):
            if "budget_envelope" in " ".join(n.get("tags", [])) or "finance" in n.get("source_agent", ""):
                budget_note = n["content"]
                break
        return [
            ExpansionStep(
                label="Reframe",
                content=(
                    f"Restate as a choice between defending the current market position vs. "
                    f"expanding into an adjacent one to address: '{problem[:80]}'."
                ),
            ),
            ExpansionStep(
                label="Constraints",
                content=(
                    "Hard: brand permission (where customers let us play). "
                    "Soft: sales enablement cycle time, partner channel coverage."
                ),
            ),
            ExpansionStep(
                label="Alternatives",
                content=(
                    "(I) Deepen in the core segment, (II) adjacent expansion via existing channel, "
                    "(III) new-channel push to a greenfield segment, (IV) partnership/white-label."
                ),
            ),
            ExpansionStep(
                label="Assumptions",
                content=(
                    "Assume the top-3 competitors can replicate any feature-level move in 2 quarters. "
                    "Durable edge must be structural: data, distribution, or switching cost."
                    + (f" Finance signal in shared context: {budget_note}" if budget_note else "")
                ),
            ),
            ExpansionStep(
                label="Edge cases",
                content=(
                    "If a competitor announces their own move first, (I) and (II) compress into "
                    "narrower windows; (IV) becomes the only viable option if we're late."
                ),
            ),
            ExpansionStep(
                label="Cross-domain analogy",
                content=(
                    "Mirrors Intel's hub-and-spoke platform move — anchor in the dominant segment, "
                    "then leverage the installed base into an adjacent one."
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
            "Anchor in the core segment (Option I) for the next 2 quarters while running a "
            "low-cost adjacent-market experiment (Option II, capped at 15% of the envelope). "
            "Go-to-market: existing channel first, measured on logo count + net dollar retention."
        )
        steps = [
            CompressionStep(
                label="Integrate",
                content=(
                    "Durable edge lives in distribution and switching cost — both are strongest in "
                    "the core. The adjacent experiment is a paid option on expansion, not a bet."
                ),
            ),
            CompressionStep(
                label="Commit",
                content=(
                    "Core deepening dominates the 6-month horizon; adjacency hedges the 12-month one."
                ),
            ),
        ]
        outputs = {
            "market_positioning": "core-anchor + adjacent-experiment",
            "go_to_market": {"primary_channel": "direct", "metrics": ["logos", "NDR"]},
        }
        return rec, steps, ConfidenceLevel.MEDIUM, (
            "Would flip to adjacent-first (Option II) if a competitor announces a core-segment move "
            "within 30 days OR if NDR drops below 110% for two consecutive quarters."
        ), outputs
