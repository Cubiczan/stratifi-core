#!/usr/bin/env python3
"""DeltaFin Chat MVP — extended demo exercising all 3 variance modes with CHP hardening."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure we can import from src
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stratifi-core" / "src"))

from cme.chp import CHPOrchestrator, DecisionRegistry
from cme.finance import (
    # Mode 1: Original actual-vs-budget variance
    load_variance_csv,
    analyze_variance,
    build_variance_case,
    render_variance_markdown,
    render_variance_html,
    # Mode 2: Month-over-Month
    load_mom_csv,
    analyze_mom_variance,
    build_mom_variance_case,
    render_mom_variance_markdown,
    render_mom_variance_html,
    # Mode 3: Actual-vs-Forecast
    load_forecast_csv,
    analyze_forecast_variance,
    build_forecast_variance_case,
    render_forecast_variance_markdown,
    render_forecast_variance_html,
)

OUTPUT_DIR = Path(__file__).resolve().parent


def demo_mode1_actual_vs_budget():
    """Original variance-studio mode: actual vs budget with CHP gate."""
    print("=" * 72)
    print("MODE 1: Actual vs Budget Variance (original DeltaFin variant)")
    print("=" * 72)

    csv_path = OUTPUT_DIR / "variance_studio_sample.csv"
    rows, warnings = load_variance_csv(csv_path)
    result = analyze_variance(rows, period="2026-03", entity="Acme")

    registry = DecisionRegistry.load(OUTPUT_DIR / ".chp_registry_demo.json")
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_variance_case(result)
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    registry.save(OUTPUT_DIR / ".chp_registry_demo.json")

    md = render_variance_markdown(result)
    html = render_variance_html(result, session_summary=report.render())

    print(f"\nCHP Verdict: {report.r0_verdict.value}")
    print(f"Foundation Score: {report.case.foundation_score}")
    print(f"Status: {report.case.status.value}")
    print(f"Top driver: {result.spotlight_driver.driver_name if result.spotlight_driver else 'N/A'}")
    print(f" Variance: {result.spotlight_driver.variance:,.0f}" if result.spotlight_driver else "")
    print(f"\n--- Markdown Preview (first 500 chars) ---")
    print(md[:500])

    (OUTPUT_DIR / "demo_mode1_output.md").write_text(md)
    (OUTPUT_DIR / "demo_mode1_output.html").write_text(html)
    print(f"\n[+] Wrote demo_mode1_output.md / .html")
    print()


def demo_mode2_mom():
    """NEW: Month-over-Month variance with CHP hardening."""
    print("=" * 72)
    print("MODE 2: Month-over-Month Variance (NEW — DeltaFin extension)")
    print("=" * 72)

    csv_path = OUTPUT_DIR / "variance_studio_mom_sample.csv"
    rows, warnings = load_mom_csv(csv_path)
    result = analyze_mom_variance(rows, entity="Acme", base_period="2026-03", compare_period="2026-02")

    registry = DecisionRegistry.load(OUTPUT_DIR / ".chp_registry_demo.json")
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_mom_variance_case(result)
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    registry.save(OUTPUT_DIR / ".chp_registry_demo.json")

    md = render_mom_variance_markdown(result)
    html = render_mom_variance_html(result, session_summary=report.render())

    print(f"\nCHP Verdict: {report.r0_verdict.value}")
    print(f"Foundation Score: {report.case.foundation_score}")
    print(f"Status: {report.case.status.value}")
    print(f"Comparing: {result.compare_period} → {result.base_period}")
    print(f"Spotlight: {result.spotlight_driver.driver_name if result.spotlight_driver else 'N/A'}")
    print(f"\n--- Trend Summary ---")
    print(result.trend_summary)
    print(f"\n--- Markdown Preview (first 500 chars) ---")
    print(md[:500])

    (OUTPUT_DIR / "demo_mode2_output.md").write_text(md)
    (OUTPUT_DIR / "demo_mode2_output.html").write_text(html)
    print(f"\n[+] Wrote demo_mode2_output.md / .html")
    print()


def demo_mode3_forecast():
    """NEW: Actual-vs-Forecast variance with CHP hardening."""
    print("=" * 72)
    print("MODE 3: Actual vs Forecast Variance (NEW — DeltaFin extension)")
    print("=" * 72)

    csv_path = OUTPUT_DIR / "variance_studio_forecast_sample.csv"
    rows, warnings = load_forecast_csv(csv_path)
    result = analyze_forecast_variance(rows, period="2026-03", entity="Acme")

    registry = DecisionRegistry.load(OUTPUT_DIR / ".chp_registry_demo.json")
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_forecast_variance_case(result)
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    registry.save(OUTPUT_DIR / ".chp_registry_demo.json")

    md = render_forecast_variance_markdown(result)
    html = render_forecast_variance_html(result, session_summary=report.render())

    print(f"\nCHP Verdict: {report.r0_verdict.value}")
    print(f"Foundation Score: {report.case.foundation_score}")
    print(f"Status: {report.case.status.value}")
    print(f"Forecast Accuracy Summary: {result.forecast_accuracy_summary}")
    print(f"\n--- Markdown Preview (first 500 chars) ---")
    print(md[:500])

    (OUTPUT_DIR / "demo_mode3_output.md").write_text(md)
    (OUTPUT_DIR / "demo_mode3_output.html").write_text(html)
    print(f"\n[+] Wrote demo_mode3_output.md / .html")
    print()


def main():
    print()
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     DeltaFin Chat MVP — Extended Demo (all 3 modes)          ║")
    print("║     Every mode runs through CHP R0 gate + Foundation Attack   ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()

    demo_mode1_actual_vs_budget()
    demo_mode2_mom()
    demo_mode3_forecast()

    print("=" * 72)
    print("DEMO COMPLETE — 3 variance modes, all CHP-hardened")
    print("=" * 72)
    print()
    print("Output files in examples/:")
    print("  demo_mode1_output.md/.html  — Actual vs Budget")
    print("  demo_mode2_output.md/.html  — Month over Month")
    print("  demo_mode3_output.md/.html  — Actual vs Forecast")
    print()


if __name__ == "__main__":
    main()
