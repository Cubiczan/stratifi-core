"""Tests for the investment committee scoring workflow."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.chp import CHPOrchestrator  # noqa: E402
from cme.finance.investment_committee import (  # noqa: E402
    build_investment_committee_case,
    export_investment_committee_workbook,
    load_investment_proposal,
    render_investment_committee_markdown,
    score_investment_proposal,
)


def test_investment_committee_scoring_builds():
    proposal = load_investment_proposal(Path(__file__).resolve().parents[1] / "examples" / "investment_committee_sample.json")
    result = score_investment_proposal(proposal)

    assert result.total_score > 0
    assert result.scorecard
    assert result.recommendation in {"Advance", "Advance with Conditions", "Hold", "Do Not Advance"}
    assert "Investment Committee Scoring Tool" in render_investment_committee_markdown(result)


def test_investment_committee_case_builder():
    proposal = load_investment_proposal(Path(__file__).resolve().parents[1] / "examples" / "investment_committee_sample.json")
    result = score_investment_proposal(proposal)
    case, disclosure, attack = build_investment_committee_case(result)
    report = CHPOrchestrator().run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )

    assert report.case.domain == "investment_committee"
    assert report.case.foundation_score == attack.foundation_score
    assert "BEGIN_PAYLOAD" in report.initial_packet


def test_investment_committee_workbook_export(tmp_path: Path):
    proposal = load_investment_proposal(Path(__file__).resolve().parents[1] / "examples" / "investment_committee_sample.json")
    result = score_investment_proposal(proposal)
    output = export_investment_committee_workbook(
        result,
        session_summary="CHP summary",
        output_path=tmp_path / "investment_committee.xlsx",
    )
    assert output.exists()
