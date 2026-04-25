"""Tests for the Monthly CFO Variance Studio."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.chp import CHPOrchestrator  # noqa: E402
from cme.finance import analyze_variance, build_variance_case, load_variance_csv  # noqa: E402
from cme.finance.variance_studio import render_variance_html  # noqa: E402


def test_variance_analysis_and_case_builder():
    csv_path = Path(__file__).resolve().parents[1] / "examples" / "variance_studio_sample.csv"
    rows, warnings = load_variance_csv(csv_path)
    result = analyze_variance(rows)

    assert result.period == "2026-03"
    assert result.entity == "Acme"
    assert len(result.kpis) == 3
    assert len(result.drivers) == 3
    assert result.spotlight_driver is not None
    assert result.exec_summary_bullets
    assert result.risks
    assert result.suggested_actions
    assert result.audit_trail
    assert any(driver.driver_name == "Subscription Revenue" for driver in result.drivers)
    assert isinstance(warnings, list)

    case, disclosure, attack = build_variance_case(result)
    orch = CHPOrchestrator()
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )

    assert report.case.domain == "variance_copilot"
    assert report.case.foundation_score == attack.foundation_score
    assert "BEGIN_PAYLOAD" in report.initial_packet
    assert report.case.status.value in {"EXPLORING", "REFRAME_REQUIRED", "HALT"}


def test_variance_materiality_auto_and_manual_modes():
    csv_path = Path(__file__).resolve().parents[1] / "examples" / "variance_studio_sample.csv"
    rows, _ = load_variance_csv(csv_path)

    auto_result = analyze_variance(rows, materiality_mode="auto")
    assert auto_result.materiality_mode == "auto"
    assert auto_result.shown_driver_count >= 1
    assert auto_result.visible_drivers
    assert auto_result.other_bucket is None or auto_result.other_bucket.count >= 1

    manual_result = analyze_variance(
        rows,
        materiality_mode="manual",
        abs_threshold=50_000,
        pct_threshold=0.10,
    )
    names = [driver.driver_name for driver in manual_result.visible_drivers]
    assert manual_result.materiality_mode == "manual"
    assert "Paid Search" in names
    assert manual_result.other_bucket is not None


def test_variance_markdown_contains_storyboard_sections():
    csv_path = Path(__file__).resolve().parents[1] / "examples" / "variance_studio_sample.csv"
    rows, _ = load_variance_csv(csv_path)
    result = analyze_variance(rows)
    rendered = result.to_dict()
    assert rendered["exec_summary_bullets"]
    assert rendered["risks"]
    assert rendered["opportunities"] is not None
    assert rendered["suggested_actions"]
    assert rendered["audit_trail"]


def test_variance_html_contains_dashboard_sections():
    csv_path = Path(__file__).resolve().parents[1] / "examples" / "variance_studio_sample.csv"
    rows, _ = load_variance_csv(csv_path)
    result = analyze_variance(rows)
    html = render_variance_html(result, session_summary="LOCK STATE: EXPLORING")
    assert "Monthly CFO Variance Studio" in html
    assert "KPI Summary" in html
    assert "Visible Drivers" in html
    assert "Suggested Actions" in html
    assert "LOCK STATE: EXPLORING" in html
