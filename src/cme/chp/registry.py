"""Registry for CHP decision cases — CockroachDB-backed."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from cme.chp.models import DecisionCase, SessionStatus

logger = logging.getLogger(__name__)


@dataclass
class DecisionRegistry:
    _cases: Dict[str, DecisionCase] = field(default_factory=dict)
    _use_db: bool = False

    def __post_init__(self):
        """Auto-detect CockroachDB availability."""
        if not self._use_db:
            try:
                from cme.db.cockroachdb_layer import get_session
                from cme.db.cockroachdb_layer import DecisionCaseModel as DBDecisionCase
                from cme.db.cockroachdb_layer import RoundRecordModel as DBRound
                from sqlalchemy import select
                get_session().close()
                self._use_db = True
                logger.info("CockroachDB available — registry will use distributed storage")
            except Exception:
                logger.info("CockroachDB unavailable — registry using in-memory storage")

    def add(self, case: DecisionCase) -> None:
        self._cases[case.decision_id] = case
        if self._use_db:
            self._db_upsert(case)

    def get(self, decision_id: str) -> Optional[DecisionCase]:
        case = self._cases.get(decision_id)
        if case:
            return case
        # Try loading from DB
        if self._use_db:
            return self._db_load_one(decision_id)
        return None

    def find_related(self, text: str) -> List[DecisionCase]:
        # Search local cache first
        results = self._text_search(text, list(self._cases.values()))
        if results:
            return results
        # Fall back to DB
        if self._use_db:
            all_cases = self._db_load_all()
            return self._text_search(text, all_cases)
        return []

    def locked(self) -> List[DecisionCase]:
        local = [c for c in self._cases.values() if c.status == SessionStatus.LOCKED]
        if local:
            return local
        if self._use_db:
            return [c for c in self._db_load_all() if c.status == SessionStatus.LOCKED]
        return []

    def all(self) -> List[DecisionCase]:
        if self._cases:
            return list(self._cases.values())
        if self._use_db:
            return self._db_load_all()
        return []

    def save(self, path: str | Path) -> None:
        """Save to JSON file (local cache) and CockroachDB (distributed)."""
        target = Path(path)
        data = {decision_id: case.to_dict() for decision_id, case in self._cases.items()}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2))
        # Also persist to CockroachDB
        if self._use_db:
            for case in self._cases.values():
                self._db_upsert(case)

    @classmethod
    def load(cls, path: str | Path) -> "DecisionRegistry":
        """Load from JSON file and/or CockroachDB."""
        registry = cls()
        target = Path(path)
        # Always try CockroachDB first for distributed state
        if registry._use_db:
            db_cases = registry._db_load_all()
            for case in db_cases:
                registry._cases[case.decision_id] = case
            if db_cases:
                logger.info("Loaded %d cases from CockroachDB", len(db_cases))
        # Overlay with local file (local takes precedence for uncommitted work)
        if target.exists():
            raw = json.loads(target.read_text())
            for decision_id, case_data in raw.items():
                registry._cases[decision_id] = DecisionCase.from_dict(case_data)
            logger.info("Loaded %d cases from %s", len(raw), target)
        return registry

    # --- CockroachDB helpers ---

    def _db_upsert(self, case: DecisionCase) -> None:
        """Insert or update a decision case in CockroachDB."""
        try:
            from cme.db.cockroachdb_layer import get_session, DecisionCaseModel, RoundRecordModel
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            session = get_session()
            try:
                # Upsert decision case
                case_dict = case.to_dict()
                stmt = pg_insert(DecisionCaseModel).values(
                    decision_id=case.decision_id,
                    title=case.title,
                    domain=case.domain,
                    analysis_id=case_dict.get("analysis_id", ""),
                    status=case.status.value if hasattr(case.status, "value") else str(case.status),
                    foundation_score=getattr(case, "foundation_score", None),
                    current_phase=case_dict.get("current_phase", "FOUNDATION"),
                    current_round=case_dict.get("current_round", 0),
                    dossier=case_dict.get("dossier", {}),
                    locked_decisions=case_dict.get("locked_decisions", []),
                ).on_conflict_do_update(
                    index_elements=["decision_id"],
                    set_={
                        "title": case.title,
                        "status": case.status.value if hasattr(case.status, "value") else str(case.status),
                        "foundation_score": getattr(case, "foundation_score", None),
                        "dossier": case_dict.get("dossier", {}),
                        "locked_decisions": case_dict.get("locked_decisions", []),
                    }
                )
                session.execute(stmt)
                session.commit()
            finally:
                session.close()
        except Exception as e:
            logger.warning("DB upsert failed for %s: %s", case.decision_id, e)

    def _db_load_all(self) -> List[DecisionCase]:
        """Load all decision cases from CockroachDB."""
        try:
            from cme.db.cockroachdb_layer import get_session, DecisionCaseModel
            from sqlalchemy import select

            session = get_session()
            try:
                rows = session.execute(select(DecisionCaseModel).order_by(DecisionCaseModel.created_at.desc())).scalars().all()
                cases = []
                for row in rows:
                    case_dict = {
                        "decision_id": row.decision_id,
                        "title": row.title,
                        "domain": row.domain,
                        "status": row.status,
                        "foundation_score": row.foundation_score,
                        "current_phase": row.current_phase,
                        "current_round": row.current_round,
                        "dossier": row.dossier or {},
                        "locked_decisions": row.locked_decisions or [],
                    }
                    cases.append(DecisionCase.from_dict(case_dict))
                return cases
            finally:
                session.close()
        except Exception as e:
            logger.warning("DB load failed: %s", e)
            return []

    def _db_load_one(self, decision_id: str) -> Optional[DecisionCase]:
        """Load a single decision case from CockroachDB."""
        try:
            from cme.db.cockroachdb_layer import get_session, DecisionCaseModel
            from sqlalchemy import select

            session = get_session()
            try:
                row = session.execute(select(DecisionCaseModel).where(DecisionCaseModel.decision_id == decision_id)).scalars().first()
                if not row:
                    return None
                case_dict = {
                    "decision_id": row.decision_id,
                    "title": row.title,
                    "domain": row.domain,
                    "status": row.status,
                    "foundation_score": row.foundation_score,
                    "current_phase": row.current_phase,
                    "current_round": row.current_round,
                    "dossier": row.dossier or {},
                    "locked_decisions": row.locked_decisions or [],
                }
                return DecisionCase.from_dict(case_dict)
            finally:
                session.close()
        except Exception as e:
            logger.warning("DB load failed for %s: %s", decision_id, e)
            return None

    def _text_search(self, text: str, cases: List[DecisionCase]) -> List[DecisionCase]:
        """Full-text search across cases."""
        query = text.lower()
        query_tokens = _meaningful_tokens(query)
        hits: List[DecisionCase] = []
        for case in cases:
            if query in case.title.lower() or query in case.domain.lower():
                hits.append(case)
                continue
            if case.dossier and case.dossier.core_problem and query in case.dossier.core_problem.lower():
                hits.append(case)
                continue
            haystacks = [case.title.lower(), case.domain.lower()]
            if case.dossier and case.dossier.core_problem:
                haystacks.append(case.dossier.core_problem.lower())
            if query_tokens and any(len(query_tokens & _meaningful_tokens(haystack)) >= 3 for haystack in haystacks):
                hits.append(case)
        return hits


def _meaningful_tokens(text: str) -> set[str]:
    stop = {
        "the", "and", "for", "with", "this", "that", "from", "into",
        "should", "would", "could", "team", "quarter", "new",
    }
    tokens = {
        chunk.strip("-_ ")
        for chunk in "".join(ch if ch.isalnum() else " " for ch in text.lower()).split()
    }
    return {token for token in tokens if len(token) >= 4 and token not in stop}
