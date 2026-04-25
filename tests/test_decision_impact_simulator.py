"""Tests for the CFO decision impact simulator."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.chp import CHPOrchestrator  # noqa: E402
from cme.finance.decision_impact_simulator import (  # noqa: E402
    SimulatorInputs,
    build_decision_impact_case,
    build_decision_impact_simulation,
    render_decision_impact_html,
)


def test_decision_impact_simulation_builds():
    result = build_decision_impact_simulation(SimulatorInputs())
    assert len(result.months) == 24
    assert 0 <= result.resilience_score <= 100
    assert 0 <= result.growth_health_score <= 100
    assert result.commentary
    assert "CFO Decision Impact Simulator" in render_decision_impact_html(result)


def test_decision_impact_case_builder():
    result = build_decision_impact_simulation(SimulatorInputs())
    case, disclosure, attack = build_decision_impact_case(result)
    report = CHPOrchestrator().run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    assert report.case.domain == "decision_impact_simulator"
    assert report.case.foundation_score == attack.foundation_score
    assert "BEGIN_PAYLOAD" in report.initial_packet
