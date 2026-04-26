"""Strict CHP packet, council, closure, and verification contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from cme.chp.models import DecisionCase, Phase, SessionStatus, StateSnapshot, Verdict
from cme.chp.payloads import validate_payload_envelope


MAX_ROUNDS = 5
ORIGIN_REQUIRED_SECTIONS = (
    "1. CORE_PROBLEM_STATEMENT",
    "2. PARTNER_SYSTEM_PACKET",
    "3. TRANSMISSION_CHECKLIST",
)
PARTNER_REQUIRED_SECTIONS = (
    "ITEM_AGREEMENTS",
    "WINNER_FRAMING",
    "SCORING_TABLE",
    "OBJECTIONS",
    "FRAMEWORKS",
    "CONVERGENCE_PLAN",
    "STATE_SNAPSHOT",
)


@dataclass
class ItemAgreement:
    item: str
    score: int
    status: SessionStatus
    disagreement: str = ""
    revision: str = ""
    flip_criteria: str = ""
    third_party_status: str = "N/A"

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not 0 <= self.score <= 100:
            errors.append(f"{self.item}: score must be 0-100")
        if self.status == SessionStatus.PROVISIONAL and not self.flip_criteria:
            errors.append(f"{self.item}: PROVISIONAL requires FLIP_CRITERIA")
        if self.status == SessionStatus.PROVISIONAL and self.score >= 90:
            errors.append(f"{self.item}: PROVISIONAL score must be below 90")
        if self.status == SessionStatus.PROVISIONAL_LOCK and self.score < 90:
            errors.append(f"{self.item}: PROVISIONAL_LOCK requires score >=90")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item": self.item,
            "score": self.score,
            "status": self.status.value,
            "disagreement": self.disagreement,
            "revision": self.revision,
            "flip_criteria": self.flip_criteria,
            "third_party_status": self.third_party_status,
        }


@dataclass
class ScoringOption:
    name: str
    clarity: int
    leverage: int
    risk: int
    winner: bool = False

    @property
    def total(self) -> int:
        return self.clarity + self.leverage + self.risk

    def validate(self) -> List[str]:
        errors: List[str] = []
        for label, value in (("clarity", self.clarity), ("leverage", self.leverage), ("risk", self.risk)):
            if not 0 <= value <= 10:
                errors.append(f"{self.name}: {label} must be 0-10")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "clarity": self.clarity,
            "leverage": self.leverage,
            "risk": self.risk,
            "winner": self.winner,
            "total": self.total,
        }


@dataclass
class PartnerPacket:
    item_agreements: List[ItemAgreement]
    winner_framing: str
    scoring_table: List[ScoringOption]
    objections: List[str]
    frameworks: List[str]
    convergence_plan: List[str]
    state_snapshot: StateSnapshot
    raw_payload: str = ""

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.raw_payload and not validate_payload_envelope(self.raw_payload):
            errors.append("partner packet payload envelope is invalid")
        if self.raw_payload:
            errors.extend(require_ascii(self.raw_payload))
            for section in PARTNER_REQUIRED_SECTIONS:
                if section not in self.raw_payload:
                    errors.append(f"partner packet missing section: {section}")
        for agreement in self.item_agreements:
            errors.extend(agreement.validate())
        for option in self.scoring_table:
            errors.extend(option.validate())
        winners = [option for option in self.scoring_table if option.winner]
        if len(winners) != 1:
            errors.append("SCORING_TABLE requires exactly one winner")
        if winners and len({option.total for option in self.scoring_table}) != len(self.scoring_table):
            errors.append("SCORING_TABLE cannot contain tied total scores")
        if self.state_snapshot.round_number > MAX_ROUNDS:
            errors.append("round_number exceeds max 5")
        if self.state_snapshot.round_number == MAX_ROUNDS:
            statuses = [agreement.status for agreement in self.item_agreements]
            if SessionStatus.PROVISIONAL in statuses:
                errors.append("Round 5 cannot return PROVISIONAL")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_agreements": [item.to_dict() for item in self.item_agreements],
            "winner_framing": self.winner_framing,
            "scoring_table": [item.to_dict() for item in self.scoring_table],
            "objections": self.objections,
            "frameworks": self.frameworks,
            "convergence_plan": self.convergence_plan,
            "state_snapshot": self.state_snapshot.to_dict(),
        }


@dataclass
class OriginPacketContract:
    raw_payload: str

    def validate(self) -> List[str]:
        errors: List[str] = []
        errors.extend(require_ascii(self.raw_payload))
        if not validate_payload_envelope(self.raw_payload):
            errors.append("origin payload envelope is invalid")
        for section in ORIGIN_REQUIRED_SECTIONS:
            if section not in self.raw_payload:
                errors.append(f"origin packet missing section: {section}")
        return errors


@dataclass
class CouncilSpawn:
    trigger_reason: str
    composition: List[str]
    attack_phase: List[str]
    peer_review: List[str]
    synthesized_vulnerabilities: List[str]
    feed_back_to_round: int

    @classmethod
    def maybe_spawn(cls, *, high_stakes: bool, confidence_pct: int, current_round: int) -> "CouncilSpawn | None":
        if not high_stakes or confidence_pct >= 85:
            return None
        return cls(
            trigger_reason=f"High-stakes decision with confidence {confidence_pct}% below 85%.",
            composition=[
                "Model 1 - Role: Attacker",
                "Model 2 - Role: Attacker",
                "Model 3 - Role: Synthesizer",
            ],
            attack_phase=[
                "Attack foundation assumptions.",
                "Attack evidence quality and missing data.",
                "Attack implementation risk and false consensus.",
            ],
            peer_review=[
                "Model 1 reviews Model 2 attack for missed constraints.",
                "Model 2 reviews Model 3 synthesis for over-compression.",
                "Model 3 reviews Model 1 attack for unsupported objections.",
            ],
            synthesized_vulnerabilities=[
                "Confidence is below the high-stakes threshold.",
                "At least one independent attacker is required before lock.",
                "Human verification should remain active until vulnerabilities close.",
            ],
            feed_back_to_round=min(MAX_ROUNDS, current_round + 1),
        )


@dataclass
class ConvergenceClosure:
    status: SessionStatus
    foundation_score: int | None
    locked_decisions: List[str]
    blind_spots_resolved: List[str] = field(default_factory=list)
    blind_spots_accepted: List[str] = field(default_factory=list)
    vulnerabilities_addressed: List[str] = field(default_factory=list)
    vulnerabilities_accepted_risk: List[str] = field(default_factory=list)
    session_urls: Dict[str, str] = field(default_factory=dict)
    third_party_log: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_case(cls, case: DecisionCase, *, origin_url: str = "", partner_url: str = "") -> "ConvergenceClosure":
        return cls(
            status=case.status,
            foundation_score=case.foundation_score,
            locked_decisions=list(case.locked_decisions),
            blind_spots_accepted=list(case.blind_spots),
            vulnerabilities_accepted_risk=list(case.structural_vulnerabilities),
            session_urls={"Origin": origin_url, "Partner": partner_url},
            third_party_log=[item.to_dict() for item in case.third_party_log],
        )


@dataclass
class InterruptionRecovery:
    phase: Phase
    last_section: str
    decision_state: SessionStatus
    partial_state: Dict[str, Any]
    foundation_score: int | None = None

    def options(self) -> List[str]:
        return ["A) Continue", "B) Restart Phase", "C) Next round"]


@dataclass
class VerificationChecklist:
    pre_session: List[str]
    phase_0: List[str]
    contract: List[str]
    truth: List[str]
    limits: List[str]
    validation: List[str]

    @classmethod
    def run(cls, case: DecisionCase, *, packet: str = "") -> "VerificationChecklist":
        return cls(
            pre_session=[
                "Context check executed" if case.context_check else "MISSING context check",
                "Model parity gate passed" if case.model_parity and case.model_parity.delta != "SIGNIFICANT" else "MISSING model parity pass",
            ],
            phase_0=[
                "Foundation score present" if case.foundation_score is not None else "MISSING foundation score",
                "Foundation >=70" if (case.foundation_score or 0) >= 70 else "REFRAME required",
                "Devil's advocate complete" if case.devil_advocate_rounds else "MISSING devil's advocate",
            ],
            contract=[
                "Payload envelope valid" if packet and validate_payload_envelope(packet) else "MISSING valid payload envelope",
                "State snapshot present" if case.state_snapshots else "MISSING state snapshot",
                "VCL present" if case.vcl_diagnoses else "MISSING VCL diagnosis",
            ],
            truth=[
                "Unknowns carried" if case.dossier and case.dossier.unknowns else "MISSING unknowns",
                "Structural vulnerabilities carried" if case.structural_vulnerabilities else "MISSING structural vulnerabilities",
            ],
            limits=[
                "Within max rounds" if case.current_round <= MAX_ROUNDS else "ROUND_LIMIT_EXCEEDED",
                "ASCII packet" if not packet or not require_ascii(packet) else "NON_ASCII packet",
            ],
            validation=[
                "Third-party validation present" if case.third_party_log else "PENDING third-party validation",
                "Locked only after validation" if case.status != SessionStatus.LOCKED or case.third_party_log else "LOCKED without validation",
            ],
        )

    def failures(self) -> List[str]:
        all_items = self.pre_session + self.phase_0 + self.contract + self.truth + self.limits + self.validation
        return [item for item in all_items if item.startswith(("MISSING", "REFRAME", "ROUND_LIMIT", "NON_ASCII", "PENDING", "LOCKED"))]


def require_ascii(text: str) -> List[str]:
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return ["payload must be ASCII only"]
    return []
