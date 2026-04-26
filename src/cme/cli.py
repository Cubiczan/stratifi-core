"""Command-line entry point for the Cognitive Mesh Enterprise Orchestrator."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from cme.bridge import EntryPoint
from cme.cfo_os import (
    BoardBrief,
    CFOOperatingSystem,
    CFOTaskType,
    ForecastBrief,
    InvestmentBrief,
)
from cme.chp import (
    CHPOrchestrator,
    DecisionRegistry,
    FinancialAnalysisGuard,
    Phase,
    ThirdPartyValidation,
    TriangulationRunner,
    ValidationResult,
)
from cme.context import ContextEngine, Entity, Task
from cme.finance import (
    BoardReportInput,
    OperatingModelAssumptions,
    CapitalAllocationInput,
    SaaSKPIDashboardResult,
    SimulatorInputs,
    build_ap_optimizer_case,
    build_decision_impact_case,
    build_decision_impact_simulation,
    build_board_report,
    build_board_reporting_case,
    build_13_week_cash_forecast,
    build_24_month_saas_operating_model,
    build_investment_committee_case,
    build_saas_kpi_dashboard,
    build_saas_kpi_dashboard_case,
    analyze_variance,
    build_capital_allocation_case,
    build_cash_forecast_case,
    build_saas_operating_model_case,
    build_variance_case,
    export_ap_optimizer_workbook,
    load_ap_invoices_csv,
    export_board_report_pptx,
    export_cash_forecast_input_template,
    export_cash_forecast_workbook,
    export_investment_committee_workbook,
    export_saas_kpi_dashboard_workbook,
    export_saas_operating_model_workbook,
    load_ap_csv,
    load_cash_forecast_workbook,
    load_board_report_input,
    load_investment_proposal,
    load_mrr_history_csv,
    load_opening_cash_csv,
    load_outflows_csv,
    load_payroll_csv,
    load_saas_dashboard_csv,
    load_sales_csv,
    load_settings_csv,
    load_variance_csv,
    optimize_ap_payments,
    render_ap_optimizer_markdown,
    render_decision_impact_html,
    render_decision_impact_markdown,
    render_board_report_markdown,
    render_cash_forecast_markdown,
    render_investment_committee_markdown,
    render_saas_kpi_dashboard_html,
    render_saas_kpi_dashboard_markdown,
    render_saas_operating_model_markdown,
    render_variance_html,
    render_variance_markdown,
    score_investment_proposal,
)
from cme.orchestrator import EnterpriseOrchestrator


def _registry_path(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "registry", ".chp_registry.json"))


def _guard_financial_analysis(report, *, claim: str, context: str = ""):
    guard = FinancialAnalysisGuard()
    return guard.guard_case(report.case, claim=claim, context=context)


def _guard_to_dict(guard_result) -> dict:
    return {
        "requires_human_verification": guard_result.requires_human_verification,
        "violations": guard_result.violations,
        "triangulation": {
            "status": guard_result.triangulation.status.value,
            "foundation_score": guard_result.triangulation.report.case.foundation_score,
            "findings": guard_result.triangulation.adversary_findings,
        },
    }


def _default_agents() -> List:
    # Lazy import so the CLI has no hard dependency on the demo package.
    from demo import FinanceAgent, StrategyAgent, ComplianceAgent  # noqa: WPS433

    return [FinanceAgent(), StrategyAgent(), ComplianceAgent()]


def _seed_org_context(ctx: ContextEngine) -> None:
    ctx.upsert_entity(Entity(id="org", type="org", attributes={"name": "Aperture Corp", "fiscal_year": "2026"}))
    ctx.upsert_entity(Entity(id="finance_ops", type="team", attributes={"name": "Finance Ops", "lead": "M. Osei"}))
    ctx.upsert_entity(Entity(id="gtm", type="team", attributes={"name": "Go-To-Market", "lead": "A. Rivera"}))
    ctx.upsert_entity(
        Entity(
            id="metric_ndr",
            type="metric",
            attributes={"name": "Net Dollar Retention", "current": 1.08, "target": 1.15},
        )
    )
    ctx.upsert_entity(
        Entity(id="policy_reserve", type="policy", attributes={"name": "Regulatory reserve ratio", "value": 0.12})
    )
    ctx.add_task(Task(id="T1", goal="Align on FY26 growth bet", status="in_progress", owner="exec"))


def _cmd_demo(args: argparse.Namespace) -> int:
    ctx = ContextEngine()
    _seed_org_context(ctx)
    agents = _default_agents()
    orchestrator = EnterpriseOrchestrator(agents=agents, context=ctx)

    problem = args.problem or (
        "Should we invest $4M in building a dedicated enterprise tier next quarter, "
        "or extend the existing SMB product to cover enterprise use cases?"
    )
    report = orchestrator.orchestrate(
        problem,
        entry_point=EntryPoint(args.entry_point),
        workflow_title=args.title,
    )

    if args.json:
        out = {
            "problem": report.problem,
            "duration_ms": report.duration_ms,
            "agents": [
                {
                    "name": t.agent,
                    "recommendation": t.trace.recommendation,
                    "confidence": t.trace.confidence.value,
                    "playbook_deltas": t.deltas_applied,
                }
                for t in report.turns
            ],
            "workflow": report.workflow.to_dict(),
            "statement_completeness": report.workflow.statement.completeness_report(),
        }
        sys.stdout.write(json.dumps(out, indent=2) + "\n")
    else:
        sys.stdout.write(report.render() + "\n")

    if args.out:
        Path(args.out).write_text(report.render())
        sys.stderr.write(f"\n[wrote markdown report to {args.out}]\n")
    return 0


def _cmd_playbook(args: argparse.Namespace) -> int:
    from demo import FinanceAgent, StrategyAgent, ComplianceAgent

    mapping = {
        "finance": FinanceAgent,
        "strategy": StrategyAgent,
        "compliance": ComplianceAgent,
    }
    cls = mapping.get(args.agent)
    if not cls:
        sys.stderr.write(f"Unknown agent: {args.agent}\n")
        return 2
    agent = cls()
    if args.json:
        sys.stdout.write(agent.playbook.to_json() + "\n")
    else:
        sys.stdout.write(agent.playbook.render_for_generator() + "\n")
    return 0


def _cmd_context(args: argparse.Namespace) -> int:
    ctx = ContextEngine()
    _seed_org_context(ctx)
    sys.stdout.write(ctx.dump_json() + "\n")
    return 0


def _cmd_chp_start(args: argparse.Namespace) -> int:
    registry = DecisionRegistry.load(_registry_path(args))
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_capital_allocation_case(
        CapitalAllocationInput(
            title=args.title,
            company=args.company,
            proposal_summary=args.problem,
            investment_amount_usd=args.amount,
            expected_payback_months=args.payback_months,
            minimum_runway_months=args.min_runway,
            current_runway_months=args.current_runway,
            strategic_priorities=args.priority,
            key_risks=args.risk,
            expected_upside=args.upside,
            origin_model=args.origin_model,
            partner_model=args.partner_model,
            partner_system=args.partner_system,
        )
    )
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    guard_result = _guard_financial_analysis(report, claim=args.problem, context=report.render())
    registry.save(_registry_path(args))
    if args.json:
        out = {
            "case": report.case.to_dict(),
            "foundation_disclosure": {
                "weakest_assumptions": disclosure.weakest_assumptions,
                "invalidation_conditions": disclosure.invalidation_conditions,
                "key_vulnerability": disclosure.key_vulnerability,
            },
            "foundation_attack": {
                "assumption_attacks": attack.assumption_attacks,
                "invalidation_exploitation": attack.invalidation_exploitation,
                "vulnerability_strike": attack.vulnerability_strike,
                "foundation_score": attack.foundation_score,
                "attack_summary": attack.attack_summary,
            },
            "r0_verdict": report.r0_verdict.value,
            "foundation_verdict": report.foundation_verdict.value,
            "initial_packet": report.initial_packet,
            "accuracy_guard": _guard_to_dict(guard_result),
        }
        sys.stdout.write(json.dumps(out, indent=2) + "\n")
    else:
        sys.stdout.write(report.render() + "\n\n" + guard_result.render() + "\n")
    sys.stderr.write(f"[saved CHP registry to {_registry_path(args)}]\n")
    return 0


def _cmd_chp_receive(args: argparse.Namespace) -> int:
    registry = DecisionRegistry.load(_registry_path(args))
    orch = CHPOrchestrator(registry=registry)
    packet = Path(args.packet_file).read_text()
    case = orch.receive_partner_packet(
        decision_id=args.decision_id,
        partner_packet=packet,
        phase=Phase(args.phase),
        round_number=args.round,
        payload_echo=args.payload_echo,
        snapshot_status=args.status,
    )
    registry.save(_registry_path(args))
    if args.json:
        sys.stdout.write(json.dumps(case.to_dict(), indent=2) + "\n")
    else:
        sys.stdout.write(
            f"Received packet for {case.decision_id}\n"
            f"status={case.status.value}\n"
            f"phase={case.current_phase.value}\n"
            f"round={case.current_round}\n"
        )
    return 0


def _cmd_chp_validate(args: argparse.Namespace) -> int:
    registry = DecisionRegistry.load(_registry_path(args))
    orch = CHPOrchestrator(registry=registry)
    validation = ThirdPartyValidation(
        validator=args.validator,
        item=args.item,
        challenge=args.challenge,
        result=ValidationResult(args.result),
        rationale=args.rationale,
    )
    case = orch.apply_validation(args.decision_id, validation)
    guard_result = None
    if case.domain in {
        "capital_allocation",
        "forecast",
        "board_decision",
        "variance_studio",
        "cash_forecast_13w",
        "saas_operating_model",
        "board_reporting",
        "ap_optimizer",
        "decision_impact_simulator",
        "saas_kpi_dashboard",
        "investment_committee",
    }:
        guard = FinancialAnalysisGuard()
        guard_result = guard.guard_case(case, claim=case.title, context=json.dumps(case.to_dict(), indent=2))
    registry.save(_registry_path(args))
    if args.json:
        out = {"case": case.to_dict()}
        if guard_result:
            out["accuracy_guard"] = _guard_to_dict(guard_result)
        sys.stdout.write(json.dumps(out, indent=2) + "\n")
    else:
        sys.stdout.write(
            f"Validated {case.decision_id}\n"
            f"status={case.status.value}\n"
            f"locked={', '.join(case.locked_decisions) or 'NONE'}\n"
        )
        if guard_result:
            sys.stdout.write(guard_result.render() + "\n")
    return 0


def _cmd_chp_triangulate(args: argparse.Namespace) -> int:
    context = Path(args.context_file).read_text() if args.context_file else args.context
    result = TriangulationRunner.as_adversary(
        args.claim,
        context=context,
        high_stakes=not args.not_high_stakes,
    )
    if args.json:
        out = {
            "claim": result.claim,
            "status": result.status.value,
            "case": result.report.case.to_dict(),
            "adversary_findings": result.adversary_findings,
            "council_spawn": result.council_spawn.__dict__ if result.council_spawn else None,
            "verification_failures": result.verification.failures() if result.verification else [],
        }
        sys.stdout.write(json.dumps(out, indent=2) + "\n")
    else:
        sys.stdout.write(result.render() + "\n\n" + result.report.render() + "\n")
    return 0


def _cmd_variance_copilot(args: argparse.Namespace) -> int:
    rows, load_warnings = load_variance_csv(args.csv)
    result = analyze_variance(
        rows,
        period=args.period,
        entity=args.entity,
        group_by=args.group_by,
        materiality_mode=args.materiality_mode,
        abs_threshold=args.abs_threshold,
        pct_threshold=args.pct_threshold,
    )
    if load_warnings:
        result.data_quality_warnings = list(dict.fromkeys(load_warnings + result.data_quality_warnings))

    registry = DecisionRegistry.load(_registry_path(args))
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_variance_case(
        result,
        origin_model=args.origin_model,
        partner_model=args.partner_model,
        partner_system=args.partner_system,
    )
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    analysis_markdown = render_variance_markdown(result)
    guard_result = _guard_financial_analysis(report, claim=result.ceo_narrative, context=analysis_markdown)
    registry.save(_registry_path(args))

    session_summary = report.render() + "\n\n" + guard_result.render()
    markdown_output = analysis_markdown + "\n\n" + session_summary + "\n"
    json_output = {
        "analysis": result.to_dict(),
        "case": report.case.to_dict(),
        "r0_verdict": report.r0_verdict.value,
        "foundation_verdict": report.foundation_verdict.value,
        "initial_packet": report.initial_packet,
        "accuracy_guard": _guard_to_dict(guard_result),
    }

    if args.out_md:
        Path(args.out_md).write_text(markdown_output)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(json_output, indent=2))
    if args.out_html:
        Path(args.out_html).write_text(render_variance_html(result, session_summary=session_summary))

    if args.json:
        sys.stdout.write(json.dumps(json_output, indent=2) + "\n")
    else:
        sys.stdout.write(markdown_output)
    sys.stderr.write(f"[saved CHP registry to {_registry_path(args)}]\n")
    if args.out_md:
        sys.stderr.write(f"[wrote markdown export to {args.out_md}]\n")
    if args.out_json:
        sys.stderr.write(f"[wrote json export to {args.out_json}]\n")
    if args.out_html:
        sys.stderr.write(f"[wrote html export to {args.out_html}]\n")
    return 0


def _cmd_cash_forecast_13w(args: argparse.Namespace) -> int:
    if args.input_xlsx:
        workbook_input = load_cash_forecast_workbook(args.input_xlsx)
        opening_cash = workbook_input.opening_cash
        settings = workbook_input.settings
        sales = workbook_input.sales
        ap_rows = workbook_input.ap_rows
        payroll_rows = workbook_input.payroll_rows
        outflow_rows = workbook_input.outflow_rows
    else:
        opening_cash = load_opening_cash_csv(args.opening_cash_csv)
        settings = load_settings_csv(args.settings_csv)
        sales = load_sales_csv(args.sales_csv)
        ap_rows = load_ap_csv(args.ap_csv)
        payroll_rows = load_payroll_csv(args.payroll_csv)
        outflow_rows = load_outflows_csv(args.outflows_csv)

    result = build_13_week_cash_forecast(
        opening_cash=opening_cash,
        settings=settings,
        sales=sales,
        ap_rows=ap_rows,
        payroll_rows=payroll_rows,
        outflow_rows=outflow_rows,
    )

    registry = DecisionRegistry.load(_registry_path(args))
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_cash_forecast_case(
        result,
        origin_model=args.origin_model,
        partner_model=args.partner_model,
        partner_system=args.partner_system,
    )
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    analysis_markdown = render_cash_forecast_markdown(result)
    guard_result = _guard_financial_analysis(report, claim="13-week cash forecast", context=analysis_markdown)
    registry.save(_registry_path(args))

    session_summary = report.render() + "\n\n" + guard_result.render()
    markdown_output = analysis_markdown + "\n\n" + session_summary + "\n"
    json_output = {
        "forecast": result.to_dict(),
        "case": report.case.to_dict(),
        "r0_verdict": report.r0_verdict.value,
        "foundation_verdict": report.foundation_verdict.value,
        "initial_packet": report.initial_packet,
        "accuracy_guard": _guard_to_dict(guard_result),
    }
    if args.out_md:
        Path(args.out_md).write_text(markdown_output)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(json_output, indent=2))
    if args.out_xlsx:
        export_cash_forecast_workbook(
            result,
            session_summary=session_summary,
            output_path=args.out_xlsx,
        )

    if args.json:
        sys.stdout.write(json.dumps(json_output, indent=2) + "\n")
    else:
        sys.stdout.write(markdown_output)
    sys.stderr.write(f"[saved CHP registry to {_registry_path(args)}]\n")
    if args.out_md:
        sys.stderr.write(f"[wrote markdown export to {args.out_md}]\n")
    if args.out_json:
        sys.stderr.write(f"[wrote json export to {args.out_json}]\n")
    if args.out_xlsx:
        sys.stderr.write(f"[wrote xlsx export to {args.out_xlsx}]\n")
    return 0


def _cmd_cfo_os(args: argparse.Namespace) -> int:
    registry = DecisionRegistry.load(_registry_path(args))
    ctx = ContextEngine()
    _seed_org_context(ctx)
    cfo = CFOOperatingSystem(
        agents=_default_agents(),
        registry=registry,
        context=ctx,
        company_name=args.company,
    )

    task = CFOTaskType(args.task)
    common = dict(
        title=args.title,
        company=args.company,
        problem=args.problem,
        owner=args.owner,
        origin_model=args.origin_model,
        partner_model=args.partner_model,
        partner_system=args.partner_system,
        strategic_priorities=args.priority,
        constraints=args.constraint,
    )
    if task == CFOTaskType.FORECAST:
        brief = ForecastBrief(
            **common,
            base_revenue_usd=args.base_revenue,
            base_opex_usd=args.base_opex,
            growth_assumption_pct=args.growth_pct,
            churn_assumption_pct=args.churn_pct,
            minimum_runway_months=args.min_runway,
            current_runway_months=args.current_runway,
        )
    elif task == CFOTaskType.INVESTMENT_CASE:
        brief = InvestmentBrief(
            **common,
            investment_amount_usd=args.amount or 0.0,
            expected_payback_months=args.payback_months or 18,
            minimum_runway_months=args.min_runway,
            current_runway_months=args.current_runway,
            expected_upside=args.upside,
            key_risks=args.risk,
        )
    else:
        brief = BoardBrief(
            **common,
            options=args.option or [],
            recommended_option_index=args.recommended_index,
            open_questions=args.open_question,
            prior_board_decisions=args.prior_decision,
            strategic_risks=args.risk,
        )

    report = cfo.run(brief)
    guard_result = _guard_financial_analysis(report, claim=brief.problem, context=report.render())
    registry.save(_registry_path(args))

    if args.json:
        out = {
            "task": task.value,
            "decision_id": report.case.decision_id,
            "lock_state": report.case.status.value,
            "foundation_score": report.case.foundation_score,
            "r0_verdict": report.r0_verdict.value,
            "foundation_verdict": report.foundation_verdict.value,
            "artifact_markdown": report.artifact.render(),
            "audit_entries": [
                {
                    "agent": e.agent,
                    "claim": e.claim,
                    "expansion_label": e.expansion_label,
                    "grounding_source": e.grounding_source,
                    "grounding_confidence": e.grounding_confidence,
                    "risk_flag": e.risk_flag,
                }
                for e in report.audit.entries
            ],
            "foundation_findings": report.audit.foundation_findings,
            "case": report.case.to_dict(),
            "initial_packet": report.initial_packet,
            "accuracy_guard": _guard_to_dict(guard_result),
        }
        sys.stdout.write(json.dumps(out, indent=2) + "\n")
    else:
        sys.stdout.write(report.render() + "\n\n" + guard_result.render() + "\n")

    if args.out_md:
        Path(args.out_md).write_text(report.render() + "\n\n" + guard_result.render() + "\n")
        sys.stderr.write(f"[wrote markdown report to {args.out_md}]\n")
    sys.stderr.write(f"[saved CHP registry to {_registry_path(args)}]\n")
    return 0


def _cmd_cash_forecast_13w_template(args: argparse.Namespace) -> int:
    if args.from_examples:
        root = Path(__file__).resolve().parents[2] / "examples" / "cash_13w"
        workbook = export_cash_forecast_input_template(
            output_path=args.out_xlsx,
            opening_cash=load_opening_cash_csv(root / "opening_cash.csv"),
            settings=load_settings_csv(root / "settings.csv"),
            sales=load_sales_csv(root / "sales.csv"),
            ap_rows=load_ap_csv(root / "ap.csv"),
            payroll_rows=load_payroll_csv(root / "payroll.csv"),
            outflow_rows=load_outflows_csv(root / "outflows.csv"),
        )
    else:
        workbook = export_cash_forecast_input_template(output_path=args.out_xlsx)
    sys.stdout.write(f"{workbook}\n")
    sys.stderr.write(f"[wrote input template to {workbook}]\n")
    return 0


def _cmd_saas_model_24m(args: argparse.Namespace) -> int:
    history_rows = load_mrr_history_csv(args.history_csv) if args.history_csv else []
    assumptions = OperatingModelAssumptions(
        company_name=args.company,
        opening_cash_usd=args.opening_cash,
        current_customers=args.current_customers,
        current_arpa=args.current_arpa,
        gross_margin_pct=args.gross_margin_pct,
        monthly_opex_usd=args.monthly_opex,
        current_headcount=args.current_headcount,
        horizon_months=args.horizon_months,
        default_churn_pct=args.default_churn_pct,
        starting_new_customers=args.starting_new_customers,
        new_customers_increment_per_month=args.new_customers_increment,
        arpa_step_up_usd=args.arpa_step_up,
        arpa_step_up_every_months=args.arpa_step_months,
        hires_per_wave=args.hires_per_wave,
        hire_every_months=args.hire_every_months,
        recruitment_cost_per_wave_usd=args.recruitment_cost,
        annual_salary_increase_pct=args.annual_salary_increase_pct,
        fundraise_month_number=args.fundraise_month,
        fundraise_amount_usd=args.fundraise_amount,
    )
    result = build_24_month_saas_operating_model(assumptions, history_rows=history_rows)

    registry = DecisionRegistry.load(_registry_path(args))
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_saas_operating_model_case(
        result,
        origin_model=args.origin_model,
        partner_model=args.partner_model,
        partner_system=args.partner_system,
    )
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    analysis_markdown = render_saas_operating_model_markdown(result)
    guard_result = _guard_financial_analysis(report, claim="24-month SaaS operating model", context=analysis_markdown)
    registry.save(_registry_path(args))

    session_summary = report.render() + "\n\n" + guard_result.render()
    markdown_output = analysis_markdown + "\n\n" + session_summary + "\n"
    json_output = {
        "model": result.to_dict(),
        "case": report.case.to_dict(),
        "r0_verdict": report.r0_verdict.value,
        "foundation_verdict": report.foundation_verdict.value,
        "initial_packet": report.initial_packet,
        "accuracy_guard": _guard_to_dict(guard_result),
    }
    if args.out_md:
        Path(args.out_md).write_text(markdown_output)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(json_output, indent=2))
    if args.out_xlsx:
        export_saas_operating_model_workbook(
            result,
            session_summary=session_summary,
            output_path=args.out_xlsx,
        )

    if args.json:
        sys.stdout.write(json.dumps(json_output, indent=2) + "\n")
    else:
        sys.stdout.write(markdown_output)
    sys.stderr.write(f"[saved CHP registry to {_registry_path(args)}]\n")
    if args.out_md:
        sys.stderr.write(f"[wrote markdown export to {args.out_md}]\n")
    if args.out_json:
        sys.stderr.write(f"[wrote json export to {args.out_json}]\n")
    if args.out_xlsx:
        sys.stderr.write(f"[wrote xlsx export to {args.out_xlsx}]\n")
    return 0


def _cmd_board_reporting_generator(args: argparse.Namespace) -> int:
    payload: BoardReportInput = load_board_report_input(args.input_json)
    result = build_board_report(payload)

    registry = DecisionRegistry.load(_registry_path(args))
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_board_reporting_case(
        result,
        origin_model=args.origin_model,
        partner_model=args.partner_model,
        partner_system=args.partner_system,
    )
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    analysis_markdown = render_board_report_markdown(result)
    guard_result = _guard_financial_analysis(report, claim=result.executive_takeaway, context=analysis_markdown)
    registry.save(_registry_path(args))

    session_summary = report.render() + "\n\n" + guard_result.render()
    markdown_output = analysis_markdown + "\n\n" + session_summary + "\n"
    json_output = {
        "board_report": result.to_dict(),
        "case": report.case.to_dict(),
        "r0_verdict": report.r0_verdict.value,
        "foundation_verdict": report.foundation_verdict.value,
        "initial_packet": report.initial_packet,
        "accuracy_guard": _guard_to_dict(guard_result),
    }
    if args.out_md:
        Path(args.out_md).write_text(markdown_output)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(json_output, indent=2))
    if args.out_pptx:
        export_board_report_pptx(
            result,
            session_summary=session_summary,
            output_path=args.out_pptx,
        )

    if args.json:
        sys.stdout.write(json.dumps(json_output, indent=2) + "\n")
    else:
        sys.stdout.write(markdown_output)
    sys.stderr.write(f"[saved CHP registry to {_registry_path(args)}]\n")
    if args.out_md:
        sys.stderr.write(f"[wrote markdown export to {args.out_md}]\n")
    if args.out_json:
        sys.stderr.write(f"[wrote json export to {args.out_json}]\n")
    if args.out_pptx:
        sys.stderr.write(f"[wrote pptx export to {args.out_pptx}]\n")
    return 0


def _cmd_ap_optimizer(args: argparse.Namespace) -> int:
    invoices, load_warnings = load_ap_invoices_csv(args.csv)
    result = optimize_ap_payments(
        invoices,
        cash_available=args.cash_available,
        avoid_overdue=args.avoid_overdue,
        strategic_vendors=args.strategic_vendor,
        max_vendors=args.max_vendors,
        as_of_date=datetime.strptime(args.as_of_date, "%Y-%m-%d").date() if args.as_of_date else None,
    )
    result.warnings = list(dict.fromkeys(load_warnings + result.warnings))

    registry = DecisionRegistry.load(_registry_path(args))
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_ap_optimizer_case(
        result,
        origin_model=args.origin_model,
        partner_model=args.partner_model,
        partner_system=args.partner_system,
    )
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    analysis_markdown = render_ap_optimizer_markdown(result)
    guard_result = _guard_financial_analysis(report, claim="AP cash and payables optimizer recommendation", context=analysis_markdown)
    registry.save(_registry_path(args))

    session_summary = report.render() + "\n\n" + guard_result.render()
    markdown_output = analysis_markdown + "\n\n" + session_summary + "\n"
    json_output = {
        "optimizer": result.to_dict(),
        "case": report.case.to_dict(),
        "r0_verdict": report.r0_verdict.value,
        "foundation_verdict": report.foundation_verdict.value,
        "initial_packet": report.initial_packet,
        "accuracy_guard": _guard_to_dict(guard_result),
    }
    if args.out_md:
        Path(args.out_md).write_text(markdown_output)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(json_output, indent=2))
    if args.out_xlsx:
        export_ap_optimizer_workbook(
            result,
            session_summary=session_summary,
            output_path=args.out_xlsx,
        )

    if args.json:
        sys.stdout.write(json.dumps(json_output, indent=2) + "\n")
    else:
        sys.stdout.write(markdown_output)
    sys.stderr.write(f"[saved CHP registry to {_registry_path(args)}]\n")
    if args.out_md:
        sys.stderr.write(f"[wrote markdown export to {args.out_md}]\n")
    if args.out_json:
        sys.stderr.write(f"[wrote json export to {args.out_json}]\n")
    if args.out_xlsx:
        sys.stderr.write(f"[wrote xlsx export to {args.out_xlsx}]\n")
    return 0


def _cmd_decision_impact_simulator(args: argparse.Namespace) -> int:
    inputs = SimulatorInputs(
        cash_balance=args.cash_balance,
        monthly_revenue=args.monthly_revenue,
        gross_margin_pct=args.gross_margin_pct,
        monthly_operating_expenses=args.monthly_operating_expenses,
        headcount=args.headcount,
        monthly_churn_pct=args.monthly_churn_pct,
        new_customers_per_month=args.new_customers_per_month,
        average_contract_value=args.average_contract_value,
        ar_days=args.ar_days,
        ap_days=args.ap_days,
        pricing_change_pct=args.pricing_change_pct,
        new_customer_growth_change_pct=args.new_customer_growth_change_pct,
        churn_improvement_pct=args.churn_improvement_pct,
        expansion_revenue_pct=args.expansion_revenue_pct,
        hiring_plan=args.hiring_plan,
        salary_cost_change_pct=args.salary_cost_change_pct,
        non_payroll_cost_change_pct=args.non_payroll_cost_change_pct,
        ar_days_change=args.ar_days_change,
        ap_days_change=args.ap_days_change,
        demand_shock_pct=args.demand_shock_pct,
        cost_shock_pct=args.cost_shock_pct,
        horizon_months=args.horizon_months,
    )
    result = build_decision_impact_simulation(inputs)

    registry = DecisionRegistry.load(_registry_path(args))
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_decision_impact_case(
        result,
        origin_model=args.origin_model,
        partner_model=args.partner_model,
        partner_system=args.partner_system,
    )
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    analysis_markdown = render_decision_impact_markdown(result)
    guard_result = _guard_financial_analysis(report, claim=result.commentary, context=analysis_markdown)
    registry.save(_registry_path(args))

    session_summary = report.render() + "\n\n" + guard_result.render()
    markdown_output = analysis_markdown + "\n\n" + session_summary + "\n"
    json_output = {
        "simulation": result.to_dict(),
        "case": report.case.to_dict(),
        "r0_verdict": report.r0_verdict.value,
        "foundation_verdict": report.foundation_verdict.value,
        "initial_packet": report.initial_packet,
        "accuracy_guard": _guard_to_dict(guard_result),
    }
    if args.out_md:
        Path(args.out_md).write_text(markdown_output)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(json_output, indent=2))
    if args.out_html:
        Path(args.out_html).write_text(render_decision_impact_html(result, session_summary=session_summary))

    if args.json:
        sys.stdout.write(json.dumps(json_output, indent=2) + "\n")
    else:
        sys.stdout.write(markdown_output)
    sys.stderr.write(f"[saved CHP registry to {_registry_path(args)}]\n")
    if args.out_md:
        sys.stderr.write(f"[wrote markdown export to {args.out_md}]\n")
    if args.out_json:
        sys.stderr.write(f"[wrote json export to {args.out_json}]\n")
    if args.out_html:
        sys.stderr.write(f"[wrote html export to {args.out_html}]\n")
    return 0


def _cmd_saas_kpi_dashboard(args: argparse.Namespace) -> int:
    actuals = load_saas_dashboard_csv(args.actuals_csv)
    budget = load_saas_dashboard_csv(args.budget_csv)
    result: SaaSKPIDashboardResult = build_saas_kpi_dashboard(actuals, budget)

    registry = DecisionRegistry.load(_registry_path(args))
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_saas_kpi_dashboard_case(
        result,
        origin_model=args.origin_model,
        partner_model=args.partner_model,
        partner_system=args.partner_system,
    )
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    analysis_markdown = render_saas_kpi_dashboard_markdown(result)
    guard_result = _guard_financial_analysis(report, claim="SaaS KPI dashboard", context=analysis_markdown)
    registry.save(_registry_path(args))

    session_summary = report.render() + "\n\n" + guard_result.render()
    markdown_output = analysis_markdown + "\n\n" + session_summary + "\n"
    json_output = {
        "dashboard": result.to_dict(),
        "case": report.case.to_dict(),
        "r0_verdict": report.r0_verdict.value,
        "foundation_verdict": report.foundation_verdict.value,
        "initial_packet": report.initial_packet,
        "accuracy_guard": _guard_to_dict(guard_result),
    }
    if args.out_md:
        Path(args.out_md).write_text(markdown_output)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(json_output, indent=2))
    if args.out_html:
        Path(args.out_html).write_text(render_saas_kpi_dashboard_html(result, session_summary=session_summary))
    if args.out_xlsx:
        export_saas_kpi_dashboard_workbook(
            result,
            session_summary=session_summary,
            output_path=args.out_xlsx,
        )

    if args.json:
        sys.stdout.write(json.dumps(json_output, indent=2) + "\n")
    else:
        sys.stdout.write(markdown_output)
    sys.stderr.write(f"[saved CHP registry to {_registry_path(args)}]\n")
    if args.out_md:
        sys.stderr.write(f"[wrote markdown export to {args.out_md}]\n")
    if args.out_json:
        sys.stderr.write(f"[wrote json export to {args.out_json}]\n")
    if args.out_html:
        sys.stderr.write(f"[wrote html export to {args.out_html}]\n")
    if args.out_xlsx:
        sys.stderr.write(f"[wrote xlsx export to {args.out_xlsx}]\n")
    return 0


def _cmd_investment_committee(args: argparse.Namespace) -> int:
    proposal = load_investment_proposal(args.input_json)
    result = score_investment_proposal(proposal)

    registry = DecisionRegistry.load(_registry_path(args))
    orch = CHPOrchestrator(registry=registry)
    case, disclosure, attack = build_investment_committee_case(
        result,
        origin_model=args.origin_model,
        partner_model=args.partner_model,
        partner_system=args.partner_system,
    )
    report = orch.run_initial_session(
        case=case,
        foundation_disclosure=disclosure,
        foundation_attack=attack,
    )
    analysis_markdown = render_investment_committee_markdown(result)
    guard_result = _guard_financial_analysis(report, claim=result.recommendation, context=analysis_markdown)
    registry.save(_registry_path(args))

    session_summary = report.render() + "\n\n" + guard_result.render()
    markdown_output = analysis_markdown + "\n\n" + session_summary + "\n"
    json_output = {
        "committee": result.to_dict(),
        "case": report.case.to_dict(),
        "r0_verdict": report.r0_verdict.value,
        "foundation_verdict": report.foundation_verdict.value,
        "initial_packet": report.initial_packet,
        "accuracy_guard": _guard_to_dict(guard_result),
    }
    if args.out_md:
        Path(args.out_md).write_text(markdown_output)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(json_output, indent=2))
    if args.out_xlsx:
        export_investment_committee_workbook(
            result,
            session_summary=session_summary,
            output_path=args.out_xlsx,
        )

    if args.json:
        sys.stdout.write(json.dumps(json_output, indent=2) + "\n")
    else:
        sys.stdout.write(markdown_output)
    sys.stderr.write(f"[saved CHP registry to {_registry_path(args)}]\n")
    if args.out_md:
        sys.stderr.write(f"[wrote markdown export to {args.out_md}]\n")
    if args.out_json:
        sys.stderr.write(f"[wrote json export to {args.out_json}]\n")
    if args.out_xlsx:
        sys.stderr.write(f"[wrote xlsx export to {args.out_xlsx}]\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cme",
        description="Cognitive Mesh Enterprise Orchestrator — multi-agent coordination CLI.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demo", help="Run an end-to-end orchestration on a sample problem.")
    d.add_argument("problem", nargs="?", help="Problem statement (uses a default if omitted).")
    d.add_argument(
        "--entry-point",
        choices=[e.value for e in EntryPoint],
        default=EntryPoint.PROBLEM.value,
    )
    d.add_argument("--title", default=None, help="Workflow title.")
    d.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    d.add_argument("--out", default=None, help="Also write the markdown report to this file.")
    d.set_defaults(func=_cmd_demo)

    pb = sub.add_parser("playbook", help="Show a seeded agent playbook.")
    pb.add_argument("agent", choices=["finance", "strategy", "compliance"])
    pb.add_argument("--json", action="store_true")
    pb.set_defaults(func=_cmd_playbook)

    c = sub.add_parser("context", help="Dump the seeded organizational context.")
    c.set_defaults(func=_cmd_context)

    chp = sub.add_parser("chp-start", help="Start a CHP capital allocation session scaffold.")
    chp.add_argument("--registry", default=".chp_registry.json", help="Registry JSON path.")
    chp.add_argument("--title", required=True, help="Decision title.")
    chp.add_argument("--company", default="Unknown Co", help="Company name.")
    chp.add_argument("--problem", required=True, help="Core capital allocation problem statement.")
    chp.add_argument("--amount", type=float, required=True, help="Investment amount in USD.")
    chp.add_argument("--payback-months", type=int, required=True, help="Expected payback period.")
    chp.add_argument("--min-runway", type=int, default=12, help="Minimum allowed runway in months.")
    chp.add_argument("--current-runway", type=int, required=True, help="Current runway in months.")
    chp.add_argument("--priority", action="append", default=[], help="Strategic priority. Repeatable.")
    chp.add_argument("--risk", action="append", default=[], help="Key risk. Repeatable.")
    chp.add_argument("--upside", action="append", default=[], help="Expected upside. Repeatable.")
    chp.add_argument("--origin-model", default="GPT-5.4")
    chp.add_argument("--partner-model", default="GPT-5-equivalent")
    chp.add_argument("--partner-system", default="Partner")
    chp.add_argument("--json", action="store_true")
    chp.set_defaults(func=_cmd_chp_start)

    chp_receive = sub.add_parser("chp-receive", help="Attach a partner packet to an existing CHP decision.")
    chp_receive.add_argument("--registry", default=".chp_registry.json", help="Registry JSON path.")
    chp_receive.add_argument("--decision-id", required=True)
    chp_receive.add_argument("--packet-file", required=True, help="Path to partner packet text file.")
    chp_receive.add_argument("--phase", type=int, choices=[0, 1, 2], required=True)
    chp_receive.add_argument("--round", type=int, required=True)
    chp_receive.add_argument(
        "--status",
        choices=["EXPLORING", "PROVISIONAL", "PROVISIONAL_LOCK", "LOCKED", "UNRESOLVED"],
        default="EXPLORING",
    )
    chp_receive.add_argument("--payload-echo", default="")
    chp_receive.add_argument("--json", action="store_true")
    chp_receive.set_defaults(func=_cmd_chp_receive)

    chp_validate = sub.add_parser("chp-validate", help="Apply third-party validation to a CHP decision.")
    chp_validate.add_argument("--registry", default=".chp_registry.json", help="Registry JSON path.")
    chp_validate.add_argument("--decision-id", required=True)
    chp_validate.add_argument("--validator", required=True)
    chp_validate.add_argument("--item", required=True)
    chp_validate.add_argument("--challenge", required=True)
    chp_validate.add_argument("--result", choices=["CONFIRM", "REJECT"], required=True)
    chp_validate.add_argument("--rationale", required=True)
    chp_validate.add_argument("--json", action="store_true")
    chp_validate.set_defaults(func=_cmd_chp_validate)

    chp_tri = sub.add_parser("chp-triangulate", help="Run a standalone CHP adversary/fact-check pass on a claim.")
    chp_tri.add_argument("--claim", required=True, help="Claim or recommendation to attack.")
    chp_tri.add_argument("--context", default="", help="Optional context string.")
    chp_tri.add_argument("--context-file", default=None, help="Optional file containing context for the claim.")
    chp_tri.add_argument("--not-high-stakes", action="store_true", help="Disable high-stakes council-spawn trigger.")
    chp_tri.add_argument("--json", action="store_true")
    chp_tri.set_defaults(func=_cmd_chp_triangulate)

    variance = sub.add_parser("variance-studio", help="Run the Monthly CFO Variance Studio on a CSV file.")
    variance.add_argument("--registry", default=".chp_registry.json", help="Registry JSON path.")
    variance.add_argument("--csv", required=True, help="CSV with period, entity, department, account, category, actual, budget.")
    variance.add_argument("--period", default=None, help="Analysis period. Defaults to latest in file.")
    variance.add_argument("--entity", default=None, help="Entity name. Defaults to first entity in file.")
    variance.add_argument("--group-by", choices=["account", "department"], default="account")
    variance.add_argument("--materiality-mode", choices=["auto", "manual"], default="auto")
    variance.add_argument("--abs-threshold", type=float, default=None, help="Absolute variance threshold for manual mode.")
    variance.add_argument("--pct-threshold", type=float, default=None, help="Variance percentage threshold for manual mode, expressed as decimal.")
    variance.add_argument("--origin-model", default="GPT-5.4")
    variance.add_argument("--partner-model", default="GPT-5-equivalent")
    variance.add_argument("--partner-system", default="Partner")
    variance.add_argument("--out-md", default=None, help="Optional markdown export path.")
    variance.add_argument("--out-json", default=None, help="Optional JSON export path.")
    variance.add_argument("--out-html", default=None, help="Optional HTML dashboard export path.")
    variance.add_argument("--json", action="store_true")
    variance.set_defaults(func=_cmd_variance_copilot)

    cash13 = sub.add_parser("cash-forecast-13w", help="Run the 13-week cash forecast engine on CSV inputs.")
    cash13.add_argument("--registry", default=".chp_registry.json", help="Registry JSON path.")
    cash13.add_argument("--input-xlsx", default=None, help="Single Excel workbook with required cash forecast sheets.")
    cash13.add_argument("--opening-cash-csv", default=None)
    cash13.add_argument("--settings-csv", default=None)
    cash13.add_argument("--sales-csv", default=None)
    cash13.add_argument("--ap-csv", default=None)
    cash13.add_argument("--payroll-csv", default=None)
    cash13.add_argument("--outflows-csv", default=None)
    cash13.add_argument("--origin-model", default="GPT-5.4")
    cash13.add_argument("--partner-model", default="GPT-5-equivalent")
    cash13.add_argument("--partner-system", default="Partner")
    cash13.add_argument("--out-md", default=None)
    cash13.add_argument("--out-json", default=None)
    cash13.add_argument("--out-xlsx", default=None)
    cash13.add_argument("--json", action="store_true")
    cash13.set_defaults(func=_cmd_cash_forecast_13w)

    cfo = sub.add_parser(
        "cfo-os",
        help="Run the Multi-Agent CFO Operating System on a forecast/investment/board task.",
    )
    cfo.add_argument("--registry", default=".chp_registry.json", help="CHP registry JSON path.")
    cfo.add_argument(
        "--task",
        choices=[t.value for t in CFOTaskType],
        required=True,
        help="CFO task type to run.",
    )
    cfo.add_argument("--title", required=True, help="Decision title.")
    cfo.add_argument("--company", default="Aperture Corp", help="Company name.")
    cfo.add_argument("--problem", required=True, help="Core problem statement.")
    cfo.add_argument("--owner", default="cfo")
    cfo.add_argument("--origin-model", default="GPT-5.4")
    cfo.add_argument("--partner-model", default="GPT-5-equivalent")
    cfo.add_argument("--partner-system", default="Partner")
    cfo.add_argument("--priority", action="append", default=[], help="Strategic priority. Repeatable.")
    cfo.add_argument("--constraint", action="append", default=[], help="Constraint. Repeatable.")
    cfo.add_argument("--min-runway", type=int, default=12, help="Runway floor in months.")
    cfo.add_argument("--current-runway", type=int, default=18, help="Current runway in months.")

    # Forecast-only fields
    cfo.add_argument("--base-revenue", type=float, default=0.0, help="(forecast) base revenue USD.")
    cfo.add_argument("--base-opex", type=float, default=0.0, help="(forecast) base opex USD.")
    cfo.add_argument("--growth-pct", type=float, default=0.20, help="(forecast) growth assumption as decimal.")
    cfo.add_argument("--churn-pct", type=float, default=0.08, help="(forecast) churn assumption as decimal.")

    # Investment-only fields
    cfo.add_argument("--amount", type=float, default=None, help="(investment_case) investment amount USD.")
    cfo.add_argument("--payback-months", type=int, default=None, help="(investment_case) expected payback months.")
    cfo.add_argument("--upside", action="append", default=[], help="(investment_case) expected upside. Repeatable.")
    cfo.add_argument("--risk", action="append", default=[], help="Key risk. Repeatable.")

    # Board-only fields
    cfo.add_argument("--option", action="append", default=[], help="(board_output) decision option. Repeatable.")
    cfo.add_argument("--recommended-index", type=int, default=0, help="(board_output) recommended option index.")
    cfo.add_argument("--open-question", action="append", default=[], help="(board_output) open question. Repeatable.")
    cfo.add_argument("--prior-decision", action="append", default=[], help="(board_output) prior board decision. Repeatable.")

    cfo.add_argument("--out-md", default=None, help="Optional markdown export path.")
    cfo.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    cfo.set_defaults(func=_cmd_cfo_os)

    cash13_template = sub.add_parser("cash-forecast-13w-template", help="Create an Excel input workbook template for the 13-week cash forecast engine.")
    cash13_template.add_argument("--out-xlsx", required=True)
    cash13_template.add_argument("--from-examples", action="store_true", help="Seed the template with the example dataset.")
    cash13_template.set_defaults(func=_cmd_cash_forecast_13w_template)

    saas24 = sub.add_parser("saas-model-24m", help="Run the 24-month SaaS operating model.")
    saas24.add_argument("--registry", default=".chp_registry.json", help="Registry JSON path.")
    saas24.add_argument("--history-csv", default=None, help="Optional SaaS MRR history CSV for driver forecasting.")
    saas24.add_argument("--company", default="coolreports.ai")
    saas24.add_argument("--opening-cash", type=float, default=1_000_000.0)
    saas24.add_argument("--current-customers", type=int, default=247)
    saas24.add_argument("--current-arpa", type=float, default=1256.0)
    saas24.add_argument("--gross-margin-pct", type=float, default=0.81)
    saas24.add_argument("--monthly-opex", type=float, default=350_000.0)
    saas24.add_argument("--current-headcount", type=int, default=31)
    saas24.add_argument("--horizon-months", type=int, default=24)
    saas24.add_argument("--default-churn-pct", type=float, default=0.02)
    saas24.add_argument("--starting-new-customers", type=int, default=10)
    saas24.add_argument("--new-customers-increment", type=int, default=1)
    saas24.add_argument("--arpa-step-up", type=float, default=50.0)
    saas24.add_argument("--arpa-step-months", type=int, default=6)
    saas24.add_argument("--hires-per-wave", type=int, default=5)
    saas24.add_argument("--hire-every-months", type=int, default=4)
    saas24.add_argument("--recruitment-cost", type=float, default=30_000.0)
    saas24.add_argument("--annual-salary-increase-pct", type=float, default=0.10)
    saas24.add_argument("--fundraise-month", type=int, default=12)
    saas24.add_argument("--fundraise-amount", type=float, default=1_000_000.0)
    saas24.add_argument("--origin-model", default="GPT-5.4")
    saas24.add_argument("--partner-model", default="GPT-5-equivalent")
    saas24.add_argument("--partner-system", default="Partner")
    saas24.add_argument("--out-md", default=None)
    saas24.add_argument("--out-json", default=None)
    saas24.add_argument("--out-xlsx", default=None)
    saas24.add_argument("--json", action="store_true")
    saas24.set_defaults(func=_cmd_saas_model_24m)

    board = sub.add_parser("board-reporting-generator", help="Generate a board-ready reporting package and PPTX deck.")
    board.add_argument("--registry", default=".chp_registry.json", help="Registry JSON path.")
    board.add_argument("--input-json", required=True, help="Structured board input JSON.")
    board.add_argument("--origin-model", default="GPT-5.4")
    board.add_argument("--partner-model", default="GPT-5-equivalent")
    board.add_argument("--partner-system", default="Partner")
    board.add_argument("--out-md", default=None)
    board.add_argument("--out-json", default=None)
    board.add_argument("--out-pptx", default=None)
    board.add_argument("--json", action="store_true")
    board.set_defaults(func=_cmd_board_reporting_generator)

    ap = sub.add_parser("ap-optimizer", help="Run the AP Cash & Payables Optimizer.")
    ap.add_argument("--registry", default=".chp_registry.json", help="Registry JSON path.")
    ap.add_argument("--csv", required=True, help="AP invoice CSV.")
    ap.add_argument("--cash-available", type=float, required=True, help="Cash available for AP this week.")
    ap.add_argument("--avoid-overdue", action="store_true", default=False)
    ap.add_argument("--strategic-vendor", action="append", default=[], help="Strategic vendor. Repeatable.")
    ap.add_argument("--max-vendors", type=int, default=10)
    ap.add_argument("--as-of-date", default=None, help="Optional YYYY-MM-DD override for aging and due-date logic.")
    ap.add_argument("--origin-model", default="GPT-5.4")
    ap.add_argument("--partner-model", default="GPT-5-equivalent")
    ap.add_argument("--partner-system", default="Partner")
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--out-xlsx", default=None)
    ap.add_argument("--json", action="store_true")
    ap.set_defaults(func=_cmd_ap_optimizer)

    sim = sub.add_parser("decision-impact-simulator", help="Run the CFO Decision Impact Simulator.")
    sim.add_argument("--registry", default=".chp_registry.json", help="Registry JSON path.")
    sim.add_argument("--cash-balance", type=float, default=1_200_000.0)
    sim.add_argument("--monthly-revenue", type=float, default=420_000.0)
    sim.add_argument("--gross-margin-pct", type=float, default=0.72)
    sim.add_argument("--monthly-operating-expenses", type=float, default=360_000.0)
    sim.add_argument("--headcount", type=int, default=28)
    sim.add_argument("--monthly-churn-pct", type=float, default=0.018)
    sim.add_argument("--new-customers-per-month", type=int, default=10)
    sim.add_argument("--average-contract-value", type=float, default=9_500.0)
    sim.add_argument("--ar-days", type=float, default=42.0)
    sim.add_argument("--ap-days", type=float, default=28.0)
    sim.add_argument("--pricing-change-pct", type=float, default=0.0)
    sim.add_argument("--new-customer-growth-change-pct", type=float, default=0.0)
    sim.add_argument("--churn-improvement-pct", type=float, default=0.0)
    sim.add_argument("--expansion-revenue-pct", type=float, default=0.02)
    sim.add_argument("--hiring-plan", choices=["freeze", "moderate", "aggressive"], default="moderate")
    sim.add_argument("--salary-cost-change-pct", type=float, default=0.0)
    sim.add_argument("--non-payroll-cost-change-pct", type=float, default=0.0)
    sim.add_argument("--ar-days-change", type=float, default=0.0)
    sim.add_argument("--ap-days-change", type=float, default=0.0)
    sim.add_argument("--demand-shock-pct", type=float, default=0.0)
    sim.add_argument("--cost-shock-pct", type=float, default=0.0)
    sim.add_argument("--horizon-months", type=int, default=24)
    sim.add_argument("--origin-model", default="GPT-5.4")
    sim.add_argument("--partner-model", default="GPT-5-equivalent")
    sim.add_argument("--partner-system", default="Partner")
    sim.add_argument("--out-md", default=None)
    sim.add_argument("--out-json", default=None)
    sim.add_argument("--out-html", default=None)
    sim.add_argument("--json", action="store_true")
    sim.set_defaults(func=_cmd_decision_impact_simulator)

    kpi = sub.add_parser("saas-kpi-dashboard", help="Build the SaaS KPI dashboard from actuals and budget CSVs.")
    kpi.add_argument("--registry", default=".chp_registry.json", help="Registry JSON path.")
    kpi.add_argument("--actuals-csv", required=True, help="Actuals KPI CSV.")
    kpi.add_argument("--budget-csv", required=True, help="Budget KPI CSV.")
    kpi.add_argument("--origin-model", default="GPT-5.4")
    kpi.add_argument("--partner-model", default="GPT-5-equivalent")
    kpi.add_argument("--partner-system", default="Partner")
    kpi.add_argument("--out-md", default=None)
    kpi.add_argument("--out-json", default=None)
    kpi.add_argument("--out-html", default=None)
    kpi.add_argument("--out-xlsx", default=None)
    kpi.add_argument("--json", action="store_true")
    kpi.set_defaults(func=_cmd_saas_kpi_dashboard)

    committee = sub.add_parser("investment-committee", help="Score a finance proposal for investment committee review.")
    committee.add_argument("--registry", default=".chp_registry.json", help="Registry JSON path.")
    committee.add_argument("--input-json", required=True, help="Structured investment proposal JSON.")
    committee.add_argument("--origin-model", default="GPT-5.4")
    committee.add_argument("--partner-model", default="GPT-5-equivalent")
    committee.add_argument("--partner-system", default="Partner")
    committee.add_argument("--out-md", default=None)
    committee.add_argument("--out-json", default=None)
    committee.add_argument("--out-xlsx", default=None)
    committee.add_argument("--json", action="store_true")
    committee.set_defaults(func=_cmd_investment_committee)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
