"""Registry for CHP decision cases."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from cme.chp.models import DecisionCase, SessionStatus


@dataclass
class DecisionRegistry:
    _cases: Dict[str, DecisionCase] = field(default_factory=dict)

    def add(self, case: DecisionCase) -> None:
        self._cases[case.decision_id] = case

    def get(self, decision_id: str) -> Optional[DecisionCase]:
        return self._cases.get(decision_id)

    def find_related(self, text: str) -> List[DecisionCase]:
        query = text.lower()
        query_tokens = _meaningful_tokens(query)
        hits: List[DecisionCase] = []
        for case in self._cases.values():
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

    def locked(self) -> List[DecisionCase]:
        return [case for case in self._cases.values() if case.status == SessionStatus.LOCKED]

    def all(self) -> List[DecisionCase]:
        return list(self._cases.values())

    def save(self, path: str | Path) -> None:
        target = Path(path)
        data = {decision_id: case.to_dict() for decision_id, case in self._cases.items()}
        target.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "DecisionRegistry":
        target = Path(path)
        if not target.exists():
            return cls()
        raw = json.loads(target.read_text())
        registry = cls()
        for decision_id, case_data in raw.items():
            registry._cases[decision_id] = DecisionCase.from_dict(case_data)
        return registry


def _meaningful_tokens(text: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "should",
        "would",
        "could",
        "team",
        "quarter",
        "new",
    }
    tokens = {
        chunk.strip("-_ ")
        for chunk in "".join(ch if ch.isalnum() else " " for ch in text.lower()).split()
    }
    return {token for token in tokens if len(token) >= 4 and token not in stop}
