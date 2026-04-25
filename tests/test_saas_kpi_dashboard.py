"""Tests for the SaaS KPI dashboard workflow."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.chp import CHPOrchestrator  # noqa: E402
from cme.finance.saas_kpi_dashboard import (  # noqa: E402
    build_saas_kpi_dashboard,
    build_saas_kpi_dashboard_case,
    export_saas_kpi_dashboard_workbook,
    load_saas_dashboard_csv,
    render_saas_kpi_dashboard_html,
)


def test_saas_kpi_dashboard_builds_and_renders():
    root = Path(__file__).resolve().parents[1] / "examples"
    actuals = load_saas_dashboard_csv(root / "saas_dashboard_actuals.csv")
    budget = load_saas_dashboard_csv(root / "saas_dashboard_budget.csv")
    result = build_saas_kpi_dashboard(actuals, budget)

    assert len(result.months) == 12
    assert len(result.kpis) >= 8
    assert result.variance_rows
    assert "SaaS KPI Dashboard" in render_saas_kpi_dashboard_html(result)


def test_saas_kpi_dashboard_case_builder():
    root = Path(__file__).resolve().parents[1] / "examples"
    result = build_saas_kpi_dashboard(
        load_saas_dashboard_csv(root / "saas_dashboard_actuals.csv"),
        load_saas_dashboard_csv(root / "saas_dashboard_budget.csv"),
    )
    case, disclosure, attack = build_saas_kpi_dashboard_case(result)
    report = CHPOrchestrator().run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )

    assert report.case.domain == "saas_kpi_dashboard"
    assert report.case.foundation_score == attack.foundation_score
    assert "BEGIN_PAYLOAD" in report.initial_packet


def test_saas_kpi_dashboard_workbook_export(tmp_path: Path):
    root = Path(__file__).resolve().parents[1] / "examples"
    result = build_saas_kpi_dashboard(
        load_saas_dashboard_csv(root / "saas_dashboard_actuals.csv"),
        load_saas_dashboard_csv(root / "saas_dashboard_budget.csv"),
    )
    output = export_saas_kpi_dashboard_workbook(
        result,
        session_summary="CHP summary",
        output_path=tmp_path / "saas_kpi_dashboard.xlsx",
    )
    assert output.exists()
