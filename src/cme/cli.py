"""Command-line entry point for the Cognitive Mesh Enterprise Orchestrator."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from cme.bridge import EntryPoint
from cme.context import ContextEngine, Entity, Task
from cme.orchestrator import EnterpriseOrchestrator


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

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
