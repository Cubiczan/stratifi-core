"""Basic smoke tests for stratifi-core (Cognitive Mesh Enterprise Orchestrator)."""

import sys
from pathlib import Path

import pytest

# Ensure src/ is on the path (matches how existing tests work)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class TestPlaybook:
    """Tests for the Playbook and Curator subsystem."""

    def test_playbook_creation(self):
        from cme.playbook import Playbook
        pb = Playbook(name="test-playbook")
        assert pb.name == "test-playbook"

    def test_reflector_creation(self):
        from cme.playbook import Reflector
        ref = Reflector()
        assert ref is not None


class TestProtocol:
    """Tests for the CognitiveMeshProtocol."""

    def test_protocol_creation(self):
        from cme.protocol import CognitiveMeshProtocol
        proto = CognitiveMeshProtocol()
        assert proto is not None

    def test_confidence_levels(self):
        from cme.protocol import ConfidenceLevel
        assert ConfidenceLevel.HIGH.value in ("high", "HIGH")
        assert ConfidenceLevel.LOW.value in ("low", "LOW")


class TestAgent:
    """Tests for MeshAgent base class."""

    def test_agent_capability(self):
        from cme.agent import AgentCapability
        cap = AgentCapability(domain="finance", produces=["recommendation"], consumes=["metrics"])
        assert cap.domain == "finance"
        assert "recommendation" in cap.produces

    def test_turn_result(self):
        from cme.agent import TurnResult
        result = TurnResult(agent="test", trace=None, deltas_applied=[], outputs={})
        assert result.agent == "test"


class TestCHPModels:
    """Tests for Consensus Hardening Protocol models."""

    def test_chp_models_import(self):
        from cme.chp.models import DecisionCase
        assert DecisionCase is not None

    def test_chp_gates_import(self):
        from cme.chp.gates import GateEvaluation
        assert GateEvaluation is not None


class TestFinance:
    """Tests for the finance module."""

    def test_cashflow_13w_import(self):
        from cme.finance.cashflow_13w import CashForecast13WResult
        assert CashForecast13WResult is not None

    def test_variance_studio_import(self):
        from cme.finance.variance_studio import VarianceStudioResult
        assert VarianceStudioResult is not None
