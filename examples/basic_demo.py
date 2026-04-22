"""Minimal end-to-end example showing the orchestrator in ~20 lines."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cme.bridge import EntryPoint
from cme.context import ContextEngine, Entity
from cme.orchestrator import EnterpriseOrchestrator
from demo import ComplianceAgent, FinanceAgent, StrategyAgent


def main() -> None:
    ctx = ContextEngine()
    ctx.upsert_entity(Entity(id="org", type="org", attributes={"name": "Aperture Corp"}))
    ctx.upsert_entity(
        Entity(id="ndr", type="metric", attributes={"name": "Net Dollar Retention", "current": 1.08})
    )

    orch = EnterpriseOrchestrator(
        agents=[FinanceAgent(), StrategyAgent(), ComplianceAgent()],
        context=ctx,
    )
    report = orch.orchestrate(
        "Should we launch a dedicated enterprise tier next quarter?",
        entry_point=EntryPoint.OPPORTUNITY,
    )
    print(report.render())


if __name__ == "__main__":
    main()
