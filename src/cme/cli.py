"""Command-line entry point for the Cognitive Mesh Enterprise Orchestrator."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from cme.bridge import EntryPoint
from cme.chp import CHPOrchestrator, DecisionRegistry, Phase, ThirdPartyValidation, ValidationResult
from cme.context import ContextEngine, Entity, Task
from cme.finance import (
    CapitalAllocationInput,
    analyze_variance,
    build_capital_allocation_case,
    build_variance_case,
    load_variance_csv,
    render_variance_html,
    render_variance_markdown,
)
from cme.orchestrator import EnterpriseOrchestrator


def _registry_path(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "registry", ".chp_registry.json"))


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
        }
        sys.stdout.write(json.dumps(out, indent=2) + "\n")
    else:
        sys.stdout.write(report.render() + "\n")
    registry.save(_registry_path(args))
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
    registry.save(_registry_path(args))
    if args.json:
        sys.stdout.write(json.dumps(case.to_dict(), indent=2) + "\n")
    else:
        sys.stdout.write(
            f"Validated {case.decision_id}\n"
            f"status={case.status.value}\n"
            f"locked={', '.join(case.locked_decisions) or 'NONE'}\n"
        )
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
    registry.save(_registry_path(args))

    markdown_output = render_variance_markdown(result) + "\n\n" + report.render() + "\n"
    json_output = {
        "analysis": result.to_dict(),
        "case": report.case.to_dict(),
        "r0_verdict": report.r0_verdict.value,
        "foundation_verdict": report.foundation_verdict.value,
        "initial_packet": report.initial_packet,
    }

    if args.out_md:
        Path(args.out_md).write_text(markdown_output)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(json_output, indent=2))
    if args.out_html:
        Path(args.out_html).write_text(render_variance_html(result, session_summary=report.render()))

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

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
