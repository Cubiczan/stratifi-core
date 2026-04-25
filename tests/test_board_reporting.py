"""Tests for board reporting generator."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.chp import CHPOrchestrator  # noqa: E402
from cme.finance.board_reporting import (  # noqa: E402
    build_board_report,
    build_board_reporting_case,
    export_board_report_pptx,
    load_board_report_input,
    validate_pptx,
)


def test_board_report_build_and_case():
    payload = load_board_report_input(Path(__file__).resolve().parents[1] / "examples" / "board_report_sample.json")
    result = build_board_report(payload)
    case, disclosure, attack = build_board_reporting_case(result)
    report = CHPOrchestrator().run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )

    assert result.executive_takeaway
    assert report.case.domain == "board_reporting"
    assert "BEGIN_PAYLOAD" in report.initial_packet


def test_board_report_pptx_export(tmp_path: Path):
    payload = load_board_report_input(Path(__file__).resolve().parents[1] / "examples" / "board_report_sample.json")
    result = build_board_report(payload)
    output = export_board_report_pptx(
        result,
        session_summary="CHP summary for board deck export.",
        output_path=tmp_path / "board_report_deck.pptx",
    )
    assert output.exists()
    assert validate_pptx(output)
