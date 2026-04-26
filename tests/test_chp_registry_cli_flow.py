"""Persistence-oriented tests for CHP registry-backed flows."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.chp import (  # noqa: E402
    CHPOrchestrator,
    DecisionRegistry,
    Phase,
    SessionStatus,
    ThirdPartyValidation,
    ValidationResult,
)
from cme.finance import CapitalAllocationInput, build_capital_allocation_case  # noqa: E402


def test_registry_persists_received_packet_and_validation(tmp_path):
    registry_path = tmp_path / "registry.json"
    registry = DecisionRegistry()
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_capital_allocation_case(
        CapitalAllocationInput(
            title="Fund enterprise workflow",
            company="Acme",
            proposal_summary="Should we fund a new enterprise workflow team this quarter?",
            investment_amount_usd=2_500_000,
            expected_payback_months=14,
            minimum_runway_months=12,
            current_runway_months=18,
            strategic_priorities=["Expand enterprise ARR"],
            key_risks=["Adoption lag"],
            expected_upside=["Higher ACV"],
        )
    )
    report = orch.run_initial_session(case=case, foundation_disclosure=disclosure, foundation_attack=attack)
    registry.save(registry_path)

    loaded = DecisionRegistry.load(registry_path)
    orch2 = CHPOrchestrator(registry=loaded)
    packet = "BEGIN_PAYLOAD [RX] [ABC123]\npartner body\nEND_PAYLOAD [RX] [ABC123]"
    updated = orch2.receive_partner_packet(
        decision_id=report.case.decision_id,
        partner_packet=packet,
        phase=Phase.SPEC,
        round_number=1,
        payload_echo="[RX] [ABC123] CONFIRMED",
        snapshot_status="PROVISIONAL_LOCK",
    )
    assert updated.current_round == 1
    assert updated.rounds[-1].payload_id == "ABC123"
    assert updated.rounds[-1].state_snapshot["PAYLOAD_ECHO"] == "[RX] [ABC123] CONFIRMED"
    assert updated.state_snapshots[-1].status.value == "PROVISIONAL_LOCK"

    orch2.apply_validation(
        updated.decision_id,
        ThirdPartyValidation(
            validator="fresh_instance",
            item="Investment spec v1",
            challenge="downside stress",
            result=ValidationResult.CONFIRM,
            rationale="still coherent",
        ),
    )
    loaded.save(registry_path)

    reloaded = DecisionRegistry.load(registry_path)
    final = reloaded.get(updated.decision_id)
    assert final is not None
    assert final.status.value == "LOCKED"
    assert "Investment spec v1" in final.locked_decisions


def test_duplicate_context_halts_and_related_autopopulates(tmp_path):
    registry = DecisionRegistry()
    orch = CHPOrchestrator(registry=registry)
    case1, disclosure1, attack1 = build_capital_allocation_case(
        CapitalAllocationInput(
            title="Fund enterprise workflow",
            company="Acme",
            proposal_summary="Should we fund a new enterprise workflow team this quarter?",
            investment_amount_usd=2_500_000,
            expected_payback_months=14,
            minimum_runway_months=12,
            current_runway_months=18,
            strategic_priorities=["Expand enterprise ARR"],
            key_risks=["Adoption lag"],
            expected_upside=["Higher ACV"],
        )
    )
    report1 = orch.run_initial_session(case=case1, foundation_disclosure=disclosure1, foundation_attack=attack1)
    orch.receive_partner_packet(
        decision_id=report1.case.decision_id,
        partner_packet="BEGIN_PAYLOAD [RX] [ABC123]\npartner body\nEND_PAYLOAD [RX] [ABC123]",
        phase=Phase.SPEC,
        round_number=1,
        payload_echo="[RX] [ABC123] CONFIRMED",
        snapshot_status="PROVISIONAL_LOCK",
    )
    orch.apply_validation(
        report1.case.decision_id,
        ThirdPartyValidation(
            validator="fresh_instance",
            item="Investment spec v1",
            challenge="downside stress",
            result=ValidationResult.CONFIRM,
            rationale="still coherent",
        ),
    )

    case2, disclosure2, attack2 = build_capital_allocation_case(
        CapitalAllocationInput(
            title="Fund enterprise workflow",
            company="Acme",
            proposal_summary="Should we fund a new enterprise workflow team this quarter?",
            investment_amount_usd=2_500_000,
            expected_payback_months=14,
            minimum_runway_months=12,
            current_runway_months=18,
            strategic_priorities=[],
            key_risks=[],
            expected_upside=[],
        )
    )
    report2 = orch.run_initial_session(case=case2, foundation_disclosure=disclosure2, foundation_attack=attack2)
    assert report2.case.status.value == "HALT"

    case3, disclosure3, attack3 = build_capital_allocation_case(
        CapitalAllocationInput(
            title="Fund analytics workflow",
            company="Acme",
            proposal_summary="Should we fund a new enterprise workflow team this quarter?",
            investment_amount_usd=2_000_000,
            expected_payback_months=12,
            minimum_runway_months=12,
            current_runway_months=18,
            strategic_priorities=[],
            key_risks=[],
            expected_upside=[],
        )
    )
    report3 = orch.run_initial_session(case=case3, foundation_disclosure=disclosure3, foundation_attack=attack3)
    assert "Fund enterprise workflow" in (report3.case.dossier.prior_decisions if report3.case.dossier else [])


def test_initial_session_records_devil_vcl_and_state_snapshot():
    registry = DecisionRegistry()
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_capital_allocation_case(
        CapitalAllocationInput(
            title="Fund enterprise workflow",
            company="Acme",
            proposal_summary="Should we fund a new enterprise workflow team this quarter?",
            investment_amount_usd=2_500_000,
            expected_payback_months=14,
            minimum_runway_months=12,
            current_runway_months=18,
            strategic_priorities=["Expand enterprise ARR"],
            key_risks=["Adoption lag"],
            expected_upside=["Higher ACV"],
        )
    )
    report = orch.run_initial_session(case=case, foundation_disclosure=disclosure, foundation_attack=attack)
    assert report.case.devil_advocate_rounds
    assert report.case.vcl_diagnoses
    assert report.case.state_snapshots
    assert "VCL_DIAGNOSIS" in report.initial_packet
    assert "SHAPE_LOCK" in report.initial_packet


def test_round_five_provisional_becomes_unresolved():
    registry = DecisionRegistry()
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_capital_allocation_case(
        CapitalAllocationInput(
            title="Fund enterprise workflow",
            company="Acme",
            proposal_summary="Should we fund a new enterprise workflow team this quarter?",
            investment_amount_usd=2_500_000,
            expected_payback_months=14,
            minimum_runway_months=12,
            current_runway_months=18,
            strategic_priorities=["Expand enterprise ARR"],
            key_risks=["Adoption lag"],
            expected_upside=["Higher ACV"],
        )
    )
    report = orch.run_initial_session(case=case, foundation_disclosure=disclosure, foundation_attack=attack)
    report.case.status = SessionStatus.PROVISIONAL_LOCK
    updated = orch.receive_partner_packet(
        decision_id=report.case.decision_id,
        partner_packet="BEGIN_PAYLOAD [RX] [RND005]\npartner body\nEND_PAYLOAD [RX] [RND005]",
        phase=Phase.IMPLEMENTATION,
        round_number=5,
        payload_echo="[RX] [RND005] CONFIRMED",
        snapshot_status="PROVISIONAL",
    )
    assert updated.status.value == "UNRESOLVED"
