"""Devil's advocate helpers for CHP sessions."""
from __future__ import annotations

from cme.chp.models import (
    DecisionCase,
    DevilsAdvocateRound,
    FoundationAttack,
    FoundationDisclosure,
    Phase,
    SessionStatus,
    StateSnapshot,
    VCLDiagnosis,
)


def merge_structural_vulnerabilities(existing: list[str], new_items: list[str]) -> list[str]:
    merged = list(existing)
    for item in new_items:
        if item not in merged:
            merged.append(item)
    return merged


def build_phase0_devils_advocate(
    disclosure: FoundationDisclosure,
    attack: FoundationAttack,
) -> DevilsAdvocateRound:
    vulnerabilities = [
        attack.vulnerability_strike,
        *(attack.assumption_attacks[:2]),
    ]
    return DevilsAdvocateRound(
        phase=Phase.FOUNDATION,
        round_number=0,
        why_direction_wrong=attack.vulnerability_strike,
        what_not_seeing=(
            disclosure.invalidation_conditions[0]
            if disclosure.invalidation_conditions
            else "The invalidation path is under-specified."
        ),
        false_consensus_risk=(
            "Foundation agreement may reflect shared optimism unless the disclosed weak assumptions survive attack."
        ),
        structural_vulnerabilities=[item for item in vulnerabilities if item][:3],
    )


def build_round3_devils_advocate(case: DecisionCase) -> DevilsAdvocateRound:
    return DevilsAdvocateRound(
        phase=Phase.IMPLEMENTATION,
        round_number=3,
        why_direction_wrong="Implementation QA can drift from the locked spec if acceptance criteria are not explicit.",
        what_not_seeing="Operational handoffs, owner capacity, and evidence quality can fail below the visible decision layer.",
        false_consensus_risk="A clean spec lock can create premature confidence that implementation risk has been resolved.",
        structural_vulnerabilities=case.structural_vulnerabilities[:3],
    )


def build_vcl_diagnoses(case: DecisionCase) -> list[VCLDiagnosis]:
    if not case.dossier:
        return []
    items = case.dossier.scope or [case.title]
    constraint = case.dossier.constraints[0] if case.dossier.constraints else "No governing constraint was supplied."
    diagnoses: list[VCLDiagnosis] = []
    for item in items[:5]:
        diagnoses.append(
            VCLDiagnosis(
                item=item,
                symptom_altitude="R2 Task",
                constraint_altitude="R4 System",
                diagnosis=(
                    f"Lower task fixes fail unless the system constraint is handled first: {constraint}"
                ),
            )
        )
    return diagnoses


def build_state_snapshot(
    case: DecisionCase,
    *,
    payload_echo: str,
    phase: Phase | None = None,
    round_number: int | None = None,
    status: SessionStatus | None = None,
) -> StateSnapshot:
    current_status = status or case.status
    provisional = [case.title] if current_status == SessionStatus.PROVISIONAL else []
    provisional_lock = [case.title] if current_status == SessionStatus.PROVISIONAL_LOCK else []
    pending = provisional_lock if not case.third_party_log else []
    return StateSnapshot(
        phase=phase or case.current_phase,
        round_number=round_number if round_number is not None else case.current_round,
        status=current_status,
        payload_echo=payload_echo,
        foundation_score=case.foundation_score,
        locked=list(case.locked_decisions),
        provisional=provisional,
        provisional_lock=provisional_lock,
        flip_active=list(case.flip_criteria),
        blind_spots_acknowledged={
            "Origin": list(case.blind_spots),
            "Partner": [],
        },
        structural_vulnerabilities=list(case.structural_vulnerabilities),
        third_party_pending=pending,
    )
