"""Cognitive Mesh Enterprise Orchestrator.

A framework for building self-improving, multi-agent enterprise AI systems that
share deep organizational context and produce executable, human-readable workflows.

Implements four composable subsystems:
    - CognitiveMeshProtocol  (expansion/compression reasoning cycles)
    - ContextEngine          (layered memory + entity/event/task schema)
    - Playbook               (ACE evolving playbooks with delta updates)
    - BridgeFramework        (multi-agent output -> executable workflow)
"""

from cme.protocol import CognitiveMeshProtocol, ReasoningTrace, ProblemType
from cme.context import ContextEngine, Entity, Event, Task
from cme.playbook import Playbook, Bullet, Reflector, Curator
from cme.bridge import BridgeFramework, Workflow, Statement
from cme.agent import MeshAgent, AgentCapability
from cme.orchestrator import EnterpriseOrchestrator

__version__ = "0.1.0"

__all__ = [
    "CognitiveMeshProtocol",
    "ReasoningTrace",
    "ProblemType",
    "ContextEngine",
    "Entity",
    "Event",
    "Task",
    "Playbook",
    "Bullet",
    "Reflector",
    "Curator",
    "BridgeFramework",
    "Workflow",
    "Statement",
    "MeshAgent",
    "AgentCapability",
    "EnterpriseOrchestrator",
]
