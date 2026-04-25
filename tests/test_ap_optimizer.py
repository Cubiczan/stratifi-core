"""Tests for the AP cash and payables optimizer."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.chp import CHPOrchestrator  # noqa: E402
from cme.finance.ap_optimizer import (  # noqa: E402
    build_ap_optimizer_case,
    export_ap_optimizer_workbook,
    load_ap_invoices_csv,
    optimize_ap_payments,
)


def test_ap_optimizer_recommendations_respect_cash_cap():
    invoices, warnings = load_ap_invoices_csv(Path(__file__).resolve().parents[1] / "examples" / "ap_invoices_sample.csv")
    result = optimize_ap_payments(
        invoices,
        cash_available=180000,
        avoid_overdue=True,
        strategic_vendors=["CloudHost", "ContractFab"],
        max_vendors=4,
        as_of_date=date(2026, 4, 18),
    )

    assert warnings
    assert result.recommended_payments
    assert sum(item.amount for item in result.recommended_payments) <= 180000
    assert len({item.vendor for item in result.recommended_payments}) <= 4
    assert result.vendor_concentration
    assert result.weekly_due_outflow
    assert result.negotiation_targets


def test_ap_optimizer_case_builder():
    invoices, _ = load_ap_invoices_csv(Path(__file__).resolve().parents[1] / "examples" / "ap_invoices_sample.csv")
    result = optimize_ap_payments(
        invoices,
        cash_available=200000,
        strategic_vendors=["CloudHost"],
        max_vendors=5,
        as_of_date=date(2026, 4, 18),
    )
    case, disclosure, attack = build_ap_optimizer_case(result)
    report = CHPOrchestrator().run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )

    assert report.case.domain == "ap_optimizer"
    assert report.case.foundation_score == attack.foundation_score
    assert "BEGIN_PAYLOAD" in report.initial_packet


def test_ap_optimizer_workbook_export(tmp_path: Path):
    invoices, _ = load_ap_invoices_csv(Path(__file__).resolve().parents[1] / "examples" / "ap_invoices_sample.csv")
    result = optimize_ap_payments(
        invoices,
        cash_available=200000,
        strategic_vendors=["CloudHost"],
        max_vendors=5,
        as_of_date=date(2026, 4, 18),
    )
    output = export_ap_optimizer_workbook(
        result,
        session_summary="CHP summary",
        output_path=tmp_path / "ap_optimizer.xlsx",
    )
    assert output.exists()
