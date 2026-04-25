"""Audit trail fusing Mesh reasoning, shared context, and CHP foundation state.

Each ``AuditEntry`` ties one fact in the final CFO artifact back to:
    - the agent that produced it,
    - the expansion step in that agent's reasoning,
    - the grounding source/confidence,
    - the CHP foundation findings that hardened or weakened it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

from cme.agent import TurnResult
from cme.chp.models import DecisionCase, FoundationAttack, FoundationDisclosure
from cme.protocol import ExpansionStep, GroundingCheck


@dataclass
class AuditEntry:
    agent: str
    claim: str
    expansion_label: str
    expansion_excerpt: str
    grounding_source: str
    grounding_confidence: str
    risk_flag: str = ""

    def render(self) -> str:
        risk = f" [RISK: {self.risk_flag}]" if self.risk_flag else ""
        return (
            f"- **{self.agent}** | {self.expansion_label} | source={self.grounding_source} "
            f"| conf={self.grounding_confidence}{risk}\n"
            f"  - claim: {self.claim}\n"
            f"  - excerpt: {self.expansion_excerpt}"
        )


@dataclass
class AuditTrail:
    entries: List[AuditEntry] = field(default_factory=list)
    foundation_findings: List[str] = field(default_factory=list)
    structural_vulnerabilities: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)
    context_writes: List[str] = field(default_factory=list)

    def render(self) -> str:
        lines = ["## Audit Trail", ""]
        if self.foundation_findings:
            lines.append("### CHP Foundation Findings")
            for f in self.foundation_findings:
                lines.append(f"- {f}")
            lines.append("")
        if self.structural_vulnerabilities:
            lines.append("### Structural Vulnerabilities")
            for v in self.structural_vulnerabilities:
                lines.append(f"- {v}")
            lines.append("")
        if self.failure_modes:
            lines.append("### Detected Failure Modes")
            for m in self.failure_modes:
                lines.append(f"- {m}")
            lines.append("")
        lines.append("### Per-Claim Provenance")
        for e in self.entries:
            lines.append(e.render())
        if self.context_writes:
            lines.append("")
            lines.append("### Shared-Context Writes")
            for w in self.context_writes:
                lines.append(f"- {w}")
        return "\n".join(lines)


def build_audit_trail(
    *,
    turns: Iterable[TurnResult],
    case: DecisionCase,
    disclosure: FoundationDisclosure,
    attack: FoundationAttack,
) -> AuditTrail:
    entries: List[AuditEntry] = []
    failure_modes: List[str] = []
    context_writes: List[str] = []

    for turn in turns:
        trace = turn.trace
        # One audit entry per expansion step: each step is a unit of reasoning.
        for step in trace.expansion:
            grounding = _grounding_for_step(step, trace.grounding)
            entries.append(
                AuditEntry(
                    agent=turn.agent,
                    claim=step.label,
                    expansion_label=step.label,
                    expansion_excerpt=step.content[:160],
                    grounding_source=grounding.source if grounding else "inferred",
                    grounding_confidence=(
                        grounding.confidence.value if grounding else trace.confidence.value
                    ),
                    risk_flag=grounding.risk_flag if grounding and grounding.risk_flag else "",
                )
            )
        # Final recommendation entry
        final_grounding = trace.grounding[-1] if trace.grounding else None
        entries.append(
            AuditEntry(
                agent=turn.agent,
                claim="recommendation",
                expansion_label="Recommendation",
                expansion_excerpt=trace.recommendation[:160],
                grounding_source=(
                    final_grounding.source if final_grounding else "inferred"
                ),
                grounding_confidence=trace.confidence.value,
                risk_flag=(
                    final_grounding.risk_flag
                    if final_grounding and final_grounding.risk_flag
                    else ""
                ),
            )
        )
        for note in turn.handoff_notes:
            if note.startswith("warning:"):
                failure_modes.append(f"{turn.agent}: {note[len('warning:'):]}")
        context_writes.append(
            f"{turn.agent} wrote recommendation to shared context (importance derived from "
            f"confidence={trace.confidence.value})"
        )

    foundation_findings = [
        f"R0 dossier scope populated: {bool(case.dossier and case.dossier.scope)}",
        f"Foundation score: {attack.foundation_score} (>=70 hardens)",
        f"Disclosed weak assumptions: {len(disclosure.weakest_assumptions)}",
        f"Attack vectors: {len(attack.assumption_attacks)}",
        f"Key vulnerability: {disclosure.key_vulnerability}",
        f"Attack summary: {attack.attack_summary}",
    ]

    return AuditTrail(
        entries=entries,
        foundation_findings=foundation_findings,
        structural_vulnerabilities=list(case.structural_vulnerabilities),
        failure_modes=failure_modes,
        context_writes=context_writes,
    )


def _grounding_for_step(
    step: ExpansionStep, grounding: List[GroundingCheck]
) -> GroundingCheck | None:
    needle = step.content[:60]
    for g in grounding:
        if g.claim.startswith(needle[:40]):
            return g
    return None
