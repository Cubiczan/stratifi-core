"""Consensus Hardening Protocol primitives.

CHP is the decision-governance layer for high-stakes, cross-model finance
workflows. This package provides the canonical data model, gate logic,
payload-integrity helpers, and an in-memory registry that higher-level finance
workflows can build on.
"""

from cme.chp.models import (
    ContextCheck,
    DecisionCase,
    DevilsAdvocateRound,
    Dossier,
    FoundationAttack,
    FoundationDisclosure,
    ModelParityCheck,
    ModelTier,
    Phase,
    RoundRecord,
    SessionStatus,
    StateSnapshot,
    ThirdPartyValidation,
    VCLDiagnosis,
    ValidationResult,
    Verdict,
)
from cme.chp.parity import assess_model_parity
from cme.chp.payloads import (
    PayloadEnvelope,
    build_payload_envelope,
    extract_payload_id,
    payload_echo_confirmed,
    validate_payload_envelope,
)
from cme.chp.accuracy import CFOAccuracyPolicy, FinancialAnalysisGuard, FinancialAnalysisGuardResult
from cme.chp.adversary_agent import AdversaryMeshAgent
from cme.chp.contracts import (
    ConvergenceClosure,
    CouncilSpawn,
    InterruptionRecovery,
    ItemAgreement,
    OriginPacketContract,
    PartnerPacket,
    ScoringOption,
    VerificationChecklist,
)
from cme.chp.gates import evaluate_phase_gate, evaluate_r0_gate
from cme.chp.orchestrator import CHPOrchestrator, CHPReport
from cme.chp.registry import DecisionRegistry
from cme.chp.runner import TriangulationResult, TriangulationRunner
from cme.chp.validators import apply_third_party_validation

__all__ = [
    "AdversaryMeshAgent",
    "CFOAccuracyPolicy",
    "ContextCheck",
    "ConvergenceClosure",
    "CouncilSpawn",
    "DecisionCase",
    "DecisionRegistry",
    "DevilsAdvocateRound",
    "Dossier",
    "FinancialAnalysisGuard",
    "FinancialAnalysisGuardResult",
    "FoundationAttack",
    "FoundationDisclosure",
    "CHPOrchestrator",
    "CHPReport",
    "InterruptionRecovery",
    "ItemAgreement",
    "ModelParityCheck",
    "ModelTier",
    "OriginPacketContract",
    "PartnerPacket",
    "Phase",
    "PayloadEnvelope",
    "RoundRecord",
    "ScoringOption",
    "SessionStatus",
    "StateSnapshot",
    "ThirdPartyValidation",
    "TriangulationResult",
    "TriangulationRunner",
    "VCLDiagnosis",
    "ValidationResult",
    "VerificationChecklist",
    "Verdict",
    "apply_third_party_validation",
    "assess_model_parity",
    "build_payload_envelope",
    "evaluate_phase_gate",
    "evaluate_r0_gate",
    "extract_payload_id",
    "payload_echo_confirmed",
    "validate_payload_envelope",
]
