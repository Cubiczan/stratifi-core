"""CFOOperatingSystem — fuses Mesh agents with CHP hardening.

A single ``run(brief)`` does the following:

    1. Builds a CHP ``DecisionCase`` + ``FoundationDisclosure`` + ``FoundationAttack``
       from the brief.
    2. Seeds the shared ``ContextEngine`` with the brief and the dossier so all
       three agents read from the same organizational view.
    3. Runs the ``EnterpriseOrchestrator`` (Finance -> Strategy -> Compliance,
       topologically sorted) so each agent contributes a reasoning trace and
       playbook deltas on shared context.
    4. Advances the CHP session: R0 gate, foundation verdict, parity assessment,
       initial payload envelope. If foundation passes and no failure modes
       triggered, the session advances to ``PROVISIONAL_LOCK``.
    5. Synthesizes a domain-specific CFO artifact tied back to every claim's
       origin via an ``AuditTrail``.

The output is a ``CFOSessionReport`` that renders to a single board-ready
markdown document.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from cme.agent import MeshAgent, TurnResult
from cme.bridge import EntryPoint
from cme.chp.foundation import foundation_verdict, validate_foundation_pair
from cme.chp.gates import evaluate_r0_gate
from cme.chp.models import (
    DecisionCase,
    FoundationAttack,
    FoundationDisclosure,
    SessionStatus,
    ThirdPartyValidation,
    ValidationResult,
    Verdict,
)
from cme.chp.orchestrator import CHPOrchestrator
from cme.chp.parity import assess_model_parity
from cme.chp.payloads import build_payload_envelope
from cme.chp.registry import DecisionRegistry
from cme.chp.validators import apply_third_party_validation
from cme.context import ContextEngine, Entity, Task
from cme.orchestrator import EnterpriseOrchestrator, OrchestrationReport

from cme.cfo_os.artifacts import (
    BoardOutput,
    CFOArtifact,
    ForecastPack,
    InvestmentCaseMemo,
    build_board_output,
    build_forecast_pack,
    build_investment_case_memo,
)
from cme.cfo_os.audit import AuditTrail, build_audit_trail
from cme.cfo_os.briefs import BoardBrief, CFOBrief, CFOTaskType, ForecastBrief, InvestmentBrief
from cme.cfo_os.dossier_builders import build_decision_case


@dataclass
class CFOSessionReport:
    brief: CFOBrief
    case: DecisionCase
    foundation_disclosure: FoundationDisclosure
    foundation_attack: FoundationAttack
    r0_verdict: Verdict
    foundation_verdict: Verdict
    initial_packet: str
    orchestration: OrchestrationReport
    artifact: CFOArtifact
    audit: AuditTrail
    turns: List[TurnResult] = field(default_factory=list)

    def render(self) -> str:
        sections = [
            "# CFO OS Session",
            f"**Task:** {self.brief.task_type.value}",
            f"**Title:** {self.brief.title}",
            f"**Company:** {self.brief.company}",
            f"**Lock state:** `{self.case.status.value}`",
            f"**Foundation score:** {self.case.foundation_score}  ·  "
            f"R0: `{self.r0_verdict.value}`  ·  Foundation: `{self.foundation_verdict.value}`",
            "",
            self.artifact.render(),
            "",
            self.audit.render(),
            "",
            "## Initial CHP Packet",
            "```",
            self.initial_packet,
            "```",
            "",
            "## Mesh Orchestration Detail",
            self.orchestration.render(),
        ]
        return "\n".join(sections)


class CFOOperatingSystem:
    """High-level CFO orchestrator. Mesh agents + CHP hardening on shared context."""

    def __init__(
        self,
        *,
        agents: List[MeshAgent],
        registry: Optional[DecisionRegistry] = None,
        context: Optional[ContextEngine] = None,
        company_name: str = "Aperture Corp",
    ) -> None:
        if not agents:
            raise ValueError("CFOOperatingSystem requires at least one MeshAgent")
        self.agents = agents
        self.registry = registry or DecisionRegistry()
        self.context = context or ContextEngine()
        self.company_name = company_name
        self._chp = CHPOrchestrator(registry=self.registry, context=self.context)
        self._mesh = EnterpriseOrchestrator(agents=self.agents, context=self.context)

    # --- Public API ------------------------------------------------------

    def run(self, brief: CFOBrief) -> CFOSessionReport:
        case, disclosure, attack = build_decision_case(brief)
        self._seed_context(brief, case)

        chp_report = self._chp.run_initial_session(
            case=case,
            foundation_disclosure=disclosure,
            foundation_attack=attack,
        )

        orchestration = self._mesh.orchestrate(
            brief.problem,
            entry_point=EntryPoint.PROBLEM,
            workflow_title=f"{brief.task_type.value}: {brief.title[:60]}",
        )

        self._advance_lock_state(chp_report.case, chp_report.foundation_verdict, orchestration.turns)

        artifact = self._build_artifact(brief, chp_report.case, orchestration.turns)
        audit = build_audit_trail(
            turns=orchestration.turns,
            case=chp_report.case,
            disclosure=disclosure,
            attack=attack,
        )

        return CFOSessionReport(
            brief=brief,
            case=chp_report.case,
            foundation_disclosure=disclosure,
            foundation_attack=attack,
            r0_verdict=chp_report.r0_verdict,
            foundation_verdict=chp_report.foundation_verdict,
            initial_packet=chp_report.initial_packet,
            orchestration=orchestration,
            artifact=artifact,
            audit=audit,
            turns=orchestration.turns,
        )

    def lock(
        self,
        decision_id: str,
        *,
        validator: str,
        item: str,
        rationale: str,
        challenge: str = "Stress test before lock progression.",
        confirm: bool = True,
    ) -> DecisionCase:
        """Apply a third-party validation; advance lock state."""
        case = self.registry.get(decision_id)
        if not case:
            raise KeyError(f"Unknown decision_id: {decision_id}")
        validation = ThirdPartyValidation(
            validator=validator,
            item=item,
            challenge=challenge,
            result=ValidationResult.CONFIRM if confirm else ValidationResult.REJECT,
            rationale=rationale,
        )
        apply_third_party_validation(case, validation)
        return case

    # --- Internals -------------------------------------------------------

    def _seed_context(self, brief: CFOBrief, case: DecisionCase) -> None:
        self.context.upsert_entity(
            Entity(
                id="org",
                type="org",
                attributes={"name": brief.company or self.company_name, "horizon": brief.horizon},
            )
        )
        self.context.upsert_entity(
            Entity(
                id=case.decision_id,
                type="decision_case",
                attributes={
                    "title": case.title,
                    "domain": case.domain,
                    "owner": case.owner,
                    "high_stakes": case.high_stakes,
                    "task_type": brief.task_type.value,
                },
            )
        )
        if case.dossier:
            for i, c in enumerate(case.dossier.constraints[:6]):
                self.context.upsert_entity(
                    Entity(
                        id=f"{case.decision_id}-constraint-{i}",
                        type="constraint",
                        attributes={"text": c},
                    )
                )
        self.context.add_task(
            Task(
                id=f"task-{case.decision_id}",
                goal=f"Harden {brief.task_type.value}: {brief.title}",
                status="in_progress",
                owner=case.owner,
            )
        )
        self.context.record_event(
            actor="cfo_os",
            action="session_open",
            object_=case.decision_id,
        )

    def _advance_lock_state(
        self, case: DecisionCase, f_verdict: Verdict, turns: List[TurnResult]
    ) -> None:
        # Foundation has to pass and no failure mode in any turn for provisional lock.
        any_failure = any(
            note.startswith("warning:") for t in turns for note in t.handoff_notes
        )
        # Don't downgrade EXISTING harder states (HALT / REFRAME) set upstream.
        if case.status in {SessionStatus.HALT, SessionStatus.REFRAME_REQUIRED}:
            return
        if f_verdict == Verdict.PASS and not any_failure:
            case.status = SessionStatus.PROVISIONAL_LOCK

    def _build_artifact(
        self, brief: CFOBrief, case: DecisionCase, turns: List[TurnResult]
    ) -> CFOArtifact:
        if isinstance(brief, ForecastBrief):
            return build_forecast_pack(brief=brief, case=case, turns=turns)
        if isinstance(brief, InvestmentBrief):
            return build_investment_case_memo(brief=brief, case=case, turns=turns)
        if isinstance(brief, BoardBrief):
            return build_board_output(brief=brief, case=case, turns=turns)
        raise TypeError(f"Unsupported brief type: {type(brief).__name__}")

    # Re-expose CHP primitives for callers that want raw access ----------

    @staticmethod
    def assess_parity(origin_model: str, partner_model: str):
        return assess_model_parity(origin_model, partner_model)

    @staticmethod
    def evaluate_r0(case: DecisionCase) -> Verdict:
        return evaluate_r0_gate(
            solvable=True,
            scoped=bool(case.dossier and case.dossier.scope),
            valid=bool(case.dossier and case.dossier.current_state),
            worth_it=case.high_stakes,
        ).verdict

    @staticmethod
    def validate_foundation(
        disclosure: FoundationDisclosure, attack: FoundationAttack
    ) -> List[str]:
        return validate_foundation_pair(disclosure, attack)

    @staticmethod
    def envelope(body: str) -> str:
        return build_payload_envelope(body).render()

    @staticmethod
    def foundation_pass(attack: FoundationAttack) -> bool:
        return foundation_verdict(attack) == Verdict.PASS
