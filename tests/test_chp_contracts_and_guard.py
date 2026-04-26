"""Tests for strict CHP contracts and CFO finance guard behavior."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.chp import (  # noqa: E402
    AdversaryMeshAgent,
    DecisionCase,
    Dossier,
    FinancialAnalysisGuard,
    ItemAgreement,
    OriginPacketContract,
    PartnerPacket,
    Phase,
    ScoringOption,
    SessionStatus,
    StateSnapshot,
    TriangulationRunner,
)
from cme.chp.payloads import build_payload_envelope  # noqa: E402
from cme.context import ContextEngine  # noqa: E402


def _case() -> DecisionCase:
    return DecisionCase(
        decision_id="finance-test",
        title="Finance test",
        domain="forecast",
        created_at=datetime.now(timezone.utc).isoformat(),
        owner="cfo",
        high_stakes=True,
        foundation_score=84,
        structural_vulnerabilities=["source definitions may drift"],
        dossier=Dossier(
            core_problem="Verify a finance recommendation.",
            goal_state=["accurate"],
            current_state=["draft"],
            constraints=["CFO accuracy floor"],
            scope=["verification"],
        ),
    )


def test_origin_contract_requires_three_sections_and_ascii():
    payload = build_payload_envelope(
        "\n".join(
            [
                "1. CORE_PROBLEM_STATEMENT",
                "Verify this.",
                "2. PARTNER_SYSTEM_PACKET",
                "From: Origin",
                "To: Partner",
                "Subject: CHP",
                "3. TRANSMISSION_CHECKLIST",
                "[ ] done",
            ]
        )
    ).render()
    assert OriginPacketContract(payload).validate() == []
    assert "ASCII" in OriginPacketContract(payload + "\nnot ascii: \u2192").validate()[0]


def test_partner_packet_enforces_single_winner_and_flip_criteria():
    snapshot = StateSnapshot(
        phase=Phase.SPEC,
        round_number=1,
        status=SessionStatus.PROVISIONAL,
        payload_echo="[RX] [ABC123] CONFIRMED",
    )
    packet = PartnerPacket(
        item_agreements=[
            ItemAgreement(
                item="Spec",
                score=84,
                status=SessionStatus.PROVISIONAL,
                flip_criteria="Source evidence changes.",
            )
        ],
        winner_framing="Advance the bounded spec.",
        scoring_table=[
            ScoringOption(name="A", clarity=9, leverage=8, risk=7, winner=True),
            ScoringOption(name="B", clarity=8, leverage=7, risk=6, winner=False),
        ],
        objections=["NONE"],
        frameworks=["DCF"],
        convergence_plan=["Validate source data."],
        state_snapshot=snapshot,
    )
    assert packet.validate() == []

    bad = PartnerPacket(
        item_agreements=[
            ItemAgreement(item="Spec", score=84, status=SessionStatus.PROVISIONAL)
        ],
        winner_framing="Advance the bounded spec.",
        scoring_table=[
            ScoringOption(name="A", clarity=9, leverage=8, risk=7, winner=True),
            ScoringOption(name="B", clarity=9, leverage=8, risk=7, winner=True),
        ],
        objections=["NONE"],
        frameworks=["DCF"],
        convergence_plan=["Validate source data."],
        state_snapshot=snapshot,
    )
    errors = bad.validate()
    assert any("FLIP_CRITERIA" in item for item in errors)
    assert any("exactly one winner" in item for item in errors)


def test_financial_guard_forces_human_verification_under_100_percent_floor():
    case = _case()
    case.status = SessionStatus.PROVISIONAL_LOCK
    result = FinancialAnalysisGuard().guard_case(
        case,
        claim="Revenue is $10M based on the operating model.",
        context="No explicit source attached.",
    )
    assert result.requires_human_verification
    assert case.status == SessionStatus.REQUIRES_HUMAN_VERIFICATION
    assert case.blind_spots


def test_triangulation_runner_and_adversary_agent_are_spawnable():
    result = TriangulationRunner.as_adversary("EBITDA improves by 20%.")
    assert result.report.case.domain == "finance_adversary"
    assert result.adversary_findings

    agent = AdversaryMeshAgent()
    turn = agent.act(
        "Verify the cash forecast recommendation.",
        shared_context=ContextEngine(),
    )
    assert turn.agent == "chp_adversary"
    assert "adversary_findings" in turn.outputs
