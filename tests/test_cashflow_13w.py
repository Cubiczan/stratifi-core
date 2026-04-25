"""Tests for the 13-week cash forecast engine."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.chp import CHPOrchestrator  # noqa: E402
from cme.finance import (  # noqa: E402
    build_13_week_cash_forecast,
    build_cash_forecast_case,
    export_cash_forecast_input_template,
    export_cash_forecast_workbook,
    load_ap_csv,
    load_cash_forecast_workbook,
    load_opening_cash_csv,
    load_outflows_csv,
    load_payroll_csv,
    load_sales_csv,
    load_settings_csv,
)


def test_cashflow_13w_forecast_and_case_builder():
    root = Path(__file__).resolve().parents[1] / "examples" / "cash_13w"
    result = build_13_week_cash_forecast(
        opening_cash=load_opening_cash_csv(root / "opening_cash.csv"),
        settings=load_settings_csv(root / "settings.csv"),
        sales=load_sales_csv(root / "sales.csv"),
        ap_rows=load_ap_csv(root / "ap.csv"),
        payroll_rows=load_payroll_csv(root / "payroll.csv"),
        outflow_rows=load_outflows_csv(root / "outflows.csv"),
    )

    assert len(result.weekly_summary) == 13
    assert result.inflows_by_week
    assert result.outflows_by_week
    assert result.driver_details

    case, disclosure, attack = build_cash_forecast_case(result)
    orch = CHPOrchestrator()
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    assert report.case.domain == "cashflow_13w"
    assert report.case.foundation_score == attack.foundation_score
    assert "BEGIN_PAYLOAD" in report.initial_packet


def test_cashflow_13w_workbook_export(tmp_path: Path):
    root = Path(__file__).resolve().parents[1] / "examples" / "cash_13w"
    result = build_13_week_cash_forecast(
        opening_cash=load_opening_cash_csv(root / "opening_cash.csv"),
        settings=load_settings_csv(root / "settings.csv"),
        sales=load_sales_csv(root / "sales.csv"),
        ap_rows=load_ap_csv(root / "ap.csv"),
        payroll_rows=load_payroll_csv(root / "payroll.csv"),
        outflow_rows=load_outflows_csv(root / "outflows.csv"),
    )

    output = export_cash_forecast_workbook(
        result,
        session_summary="CHP summary for workbook export verification.",
        output_path=tmp_path / "cash_forecast_13w.xlsx",
    )

    assert output.exists()
    with zipfile.ZipFile(output) as workbook_zip:
        names = set(workbook_zip.namelist())
    assert "xl/workbook.xml" in names


def test_cashflow_13w_input_workbook_round_trip(tmp_path: Path):
    root = Path(__file__).resolve().parents[1] / "examples" / "cash_13w"
    template = export_cash_forecast_input_template(
        output_path=tmp_path / "cash_forecast_input.xlsx",
        opening_cash=load_opening_cash_csv(root / "opening_cash.csv"),
        settings=load_settings_csv(root / "settings.csv"),
        sales=load_sales_csv(root / "sales.csv"),
        ap_rows=load_ap_csv(root / "ap.csv"),
        payroll_rows=load_payroll_csv(root / "payroll.csv"),
        outflow_rows=load_outflows_csv(root / "outflows.csv"),
    )

    workbook_input = load_cash_forecast_workbook(template)
    csv_result = build_13_week_cash_forecast(
        opening_cash=load_opening_cash_csv(root / "opening_cash.csv"),
        settings=load_settings_csv(root / "settings.csv"),
        sales=load_sales_csv(root / "sales.csv"),
        ap_rows=load_ap_csv(root / "ap.csv"),
        payroll_rows=load_payroll_csv(root / "payroll.csv"),
        outflow_rows=load_outflows_csv(root / "outflows.csv"),
    )
    workbook_result = build_13_week_cash_forecast(
        opening_cash=workbook_input.opening_cash,
        settings=workbook_input.settings,
        sales=workbook_input.sales,
        ap_rows=workbook_input.ap_rows,
        payroll_rows=workbook_input.payroll_rows,
        outflow_rows=workbook_input.outflow_rows,
    )

    assert workbook_result.to_dict() == csv_result.to_dict()
