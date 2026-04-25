"""Tests for the 24-month SaaS operating model."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.chp import CHPOrchestrator  # noqa: E402
from cme.finance.saas_operating_model import (  # noqa: E402
    OperatingModelAssumptions,
    build_24_month_saas_operating_model,
    build_saas_operating_model_case,
    export_saas_operating_model_workbook,
    load_mrr_history_csv,
)


def test_saas_operating_model_builds_with_history():
    history = load_mrr_history_csv(Path(__file__).resolve().parents[1] / "examples" / "saas_mrr_history.csv")
    assumptions = OperatingModelAssumptions(
        company_name="coolreports.ai",
        opening_cash_usd=1_000_000.0,
        current_customers=247,
        current_arpa=1256.0,
        gross_margin_pct=0.81,
        monthly_opex_usd=350_000.0,
        current_headcount=31,
    )
    result = build_24_month_saas_operating_model(assumptions, history_rows=history)

    assert len(result.driver_forecast) == 24
    assert len(result.monthly_rows) == 24
    assert result.monthly_rows[0].customers_start == 247
    assert result.monthly_rows[-1].headcount >= assumptions.current_headcount
    assert result.key_findings


def test_saas_operating_model_case_builder():
    assumptions = OperatingModelAssumptions(
        company_name="coolreports.ai",
        opening_cash_usd=1_000_000.0,
        current_customers=247,
        current_arpa=1256.0,
        gross_margin_pct=0.81,
        monthly_opex_usd=350_000.0,
        current_headcount=31,
    )
    result = build_24_month_saas_operating_model(assumptions)
    case, disclosure, attack = build_saas_operating_model_case(result)
    report = CHPOrchestrator().run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )

    assert report.case.domain == "saas_operating_model"
    assert report.case.foundation_score == attack.foundation_score
    assert "BEGIN_PAYLOAD" in report.initial_packet


def test_saas_operating_model_workbook_export(tmp_path: Path):
    assumptions = OperatingModelAssumptions(
        company_name="coolreports.ai",
        opening_cash_usd=1_000_000.0,
        current_customers=247,
        current_arpa=1256.0,
        gross_margin_pct=0.81,
        monthly_opex_usd=350_000.0,
        current_headcount=31,
    )
    result = build_24_month_saas_operating_model(assumptions)
    output = export_saas_operating_model_workbook(
        result,
        session_summary="CHP session summary",
        output_path=tmp_path / "saas_operating_model.xlsx",
    )
    assert output.exists()
