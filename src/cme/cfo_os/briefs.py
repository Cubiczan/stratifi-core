"""Structured CFO task briefs — the input to a CFO OS session."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class CFOTaskType(str, Enum):
    FORECAST = "forecast"
    INVESTMENT_CASE = "investment_case"
    BOARD_OUTPUT = "board_output"


@dataclass
class CFOBrief:
    """Common fields for any CFO task."""

    title: str
    company: str
    problem: str
    horizon: str = "FY"
    owner: str = "cfo"
    high_stakes: bool = True
    origin_system: str = "Claude"
    origin_model: str = "GPT-5.4"
    partner_system: str = "Partner"
    partner_model: str = "GPT-5-equivalent"
    decision_id: Optional[str] = None
    strategic_priorities: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)


@dataclass
class ForecastBrief(CFOBrief):
    """Driver-based forecast task."""

    task_type: CFOTaskType = CFOTaskType.FORECAST
    revenue_drivers: List[str] = field(
        default_factory=lambda: ["new logo ARR", "expansion ARR", "churn"]
    )
    cost_drivers: List[str] = field(
        default_factory=lambda: ["headcount", "infra", "go-to-market"]
    )
    base_revenue_usd: float = 0.0
    base_opex_usd: float = 0.0
    growth_assumption_pct: float = 0.20
    churn_assumption_pct: float = 0.08
    minimum_runway_months: int = 12
    current_runway_months: int = 18


@dataclass
class InvestmentBrief(CFOBrief):
    """Capital allocation / investment case task."""

    task_type: CFOTaskType = CFOTaskType.INVESTMENT_CASE
    investment_amount_usd: float = 0.0
    expected_payback_months: int = 18
    minimum_runway_months: int = 12
    current_runway_months: int = 18
    expected_upside: List[str] = field(default_factory=list)
    key_risks: List[str] = field(default_factory=list)


@dataclass
class BoardBrief(CFOBrief):
    """Board decision task — multi-option recommendation for the board."""

    task_type: CFOTaskType = CFOTaskType.BOARD_OUTPUT
    options: List[str] = field(default_factory=list)
    recommended_option_index: int = 0
    open_questions: List[str] = field(default_factory=list)
    prior_board_decisions: List[str] = field(default_factory=list)
    strategic_risks: List[str] = field(default_factory=list)
