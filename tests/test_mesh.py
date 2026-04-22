"""Smoke tests exercising the full pipeline without any external services."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.bridge import BridgeFramework, Consequences, EntryPoint, WhyLink  # noqa: E402
from cme.context import ContextEngine, Entity  # noqa: E402
from cme.orchestrator import EnterpriseOrchestrator  # noqa: E402
from cme.playbook import Bullet, DeltaOp, Playbook  # noqa: E402
from cme.protocol import (  # noqa: E402
    CognitiveMeshProtocol,
    CompressionStep,
    ConfidenceLevel,
    ExpansionStep,
    ProblemType,
    detect_hallucination_risk,
)
from demo import ComplianceAgent, FinanceAgent, StrategyAgent  # noqa: E402


def test_protocol_renders_full_trace():
    proto = CognitiveMeshProtocol()

    def _expand(p, ctx):
        return [
            ExpansionStep(label="Reframe", content="x"),
            ExpansionStep(label="Constraints", content="y"),
        ]

    def _compress(p, exp, ctx):
        return (
            "final",
            [CompressionStep(label="Integrate", content="z")],
            ConfidenceLevel.HIGH,
            "nothing changes unless Q1 slips",
        )

    trace = proto.run("plan the quarter", expansion_fn=_expand, compression_fn=_compress)
    assert trace.problem_type in ProblemType
    assert "Final Recommendation" in trace.render()
    assert trace.confidence == ConfidenceLevel.HIGH


def test_hallucination_risk_detector():
    assert detect_hallucination_risk("studies show 42% of users prefer X") is not None
    assert detect_hallucination_risk("The team shipped the feature on Tuesday.") is None


def test_playbook_add_and_dedupe():
    pb = Playbook("t")
    log1 = pb.apply(
        [DeltaOp(type="ADD", section="strategies_and_hard_rules", content="always name the owner")]
    )
    log2 = pb.apply(
        [DeltaOp(type="ADD", section="strategies_and_hard_rules", content="always name the owner")]
    )
    assert any(l.startswith("ADD") for l in log1)
    assert any(l.startswith("DEDUP") for l in log2)
    assert len(pb.bullets) == 1


def test_playbook_refine_prunes_low_utility():
    pb = Playbook("t")
    pb.bullets["shr-00001"] = Bullet(
        id="shr-00001", section="strategies_and_hard_rules", content="bad", harmful=5, helpful=1
    )
    pb.refine()
    assert "shr-00001" not in pb.bullets


def test_context_engine_selects_relevant():
    ctx = ContextEngine()
    ctx.upsert_entity(Entity(id="org", type="org", attributes={"name": "Acme"}))
    ctx.write("budget ceiling is 4M for the fiscal year", source_agent="finance", importance=0.8)
    ctx.write("sky is blue", source_agent="weather", importance=0.2)
    hits = ctx.select("what is our fiscal year budget?", k=2)
    assert any("budget" in e.content for e in hits)


def test_bridge_builds_statement_with_completeness():
    bridge = BridgeFramework()
    stmt = bridge.build_statement(
        entry_point=EntryPoint.PROBLEM,
        observable_tension="Each quarter, every product team already rebuilds the same onboarding survey.",
        whys=[
            WhyLink("why rebuild?", "no shared template"),
            WhyLink("why no template?", "no owner"),
            WhyLink("why no owner?", "missing in the RACI"),
        ],
        consequences=Consequences(
            strategic="slower launches",
            cultural="teams lose trust in shared infra",
            financial="~$200k of duplicated engineering/quarter",
        ),
        strategic_connection="Directly blocks the FY26 'one-platform' mandate.",
    )
    check = stmt.completeness_report()
    assert check["initiating_moment_specific"]
    assert check["root_cause_structural"]
    assert check["consequences_visible"]
    assert check["strategic_link"]


def test_orchestrator_end_to_end_produces_workflow():
    agents = [FinanceAgent(), StrategyAgent(), ComplianceAgent()]
    orch = EnterpriseOrchestrator(agents=agents)
    report = orch.orchestrate(
        "Should we invest in a new enterprise tier this quarter?",
        entry_point=EntryPoint.PROBLEM,
    )
    assert {t.agent for t in report.turns} == {"finance", "strategy", "compliance"}
    # Strategy depends on budget_envelope (produced by finance) -> must run after finance
    names = [t.agent for t in report.turns]
    assert names.index("finance") < names.index("strategy")
    assert names.index("strategy") < names.index("compliance")
    assert len(report.workflow.steps) == 3
    # Bridge dependency inference: later steps should list earlier producer ids
    strategy_step = next(s for s in report.workflow.steps if s.owner == "strategy")
    assert strategy_step.depends_on  # non-empty


if __name__ == "__main__":  # pragma: no cover
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
