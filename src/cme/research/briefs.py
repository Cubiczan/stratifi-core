"""Structured research brief types — the input to a ResearchWorkbench session."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ResearchTaskType(str, Enum):
    """Types of research tasks the workbench can execute."""
    COMPANY_RESEARCH = "company_research"
    SEC_DEEP_DIVE = "sec_deep_dive"
    INITIATION = "initiation_of_coverage"
    FILING_SWEEP = "filing_sweep"


@dataclass
class ResearchBrief:
    """Base class for research workbench briefs."""
    title: str
    company: str
    ticker: str
    problem: str
    industry: str = ""
    peers: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    task_type: ResearchTaskType = ResearchTaskType.COMPANY_RESEARCH
    owner: str = "research-bench"
    requestor: str = "automated"
    high_stakes: bool = True
    decision_id: Optional[str] = None
    origin_system: str = "Claude"
    origin_model: str = "GPT-5.4"
    partner_system: str = "Claude"
    partner_model: str = "GPT-5.4"


@dataclass
class CompanyBrief(ResearchBrief):
    """Business-model deep dive."""
    revenue_streams_hint: List[str] = field(default_factory=list)
    customer_segments_hint: List[str] = field(default_factory=list)
    geography_hint: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.task_type = ResearchTaskType.COMPANY_RESEARCH


@dataclass
class SECDeepDiveBrief(ResearchBrief):
    """SEC filing scan — deep dives into red-flag / governance / signals."""
    filings_in_scope: List[str] = field(default_factory=lambda: ["10-K", "10-Q", "8-K", "DEF 14A"])
    red_flag_focus: List[str] = field(default_factory=list)
    fiscal_years_back: int = 3

    def __post_init__(self) -> None:
        self.task_type = ResearchTaskType.SEC_DEEP_DIVE


@dataclass
class InitiationBrief(ResearchBrief):
    """GS-style Initiation of Coverage report."""
    rating_seed: str = "Buy"
    target_price_usd: Optional[float] = None
    valuation_method_preference: str = "EV/EBITDA"
    forecast_years: int = 3
    key_drivers_hint: List[str] = field(default_factory=list)
    investment_thesis_seed: str = ""

    def __post_init__(self) -> None:
        self.task_type = ResearchTaskType.INITIATION


@dataclass
class FilingSweepBrief(ResearchBrief):
    """Comprehensive SEC filing sweep — all 8 filing types in one pass.

    Unlike the other briefs which drive a full multi-agent CHP-hardened research
    session, the FilingSweepBrief is a data-gathering pass: it sweeps EDGAR for
    all 8 filing forms (10-K, 10-Q, 8-K, DEF 14A, S-1, 13F, Form D, PRE 14A)
    and produces a structured report.

    The output can be used as grounding data for a subsequent company_research
    or sec_deep_dive session.
    """
    task_type: ResearchTaskType = ResearchTaskType.FILING_SWEEP
    s1_limit: int = 3
    form_13f_limit: int = 2
    form_d_limit: int = 3
    pre14a_limit: int = 3
    standard_filing_limit: int = 5
    cik_override: Optional[int] = None
