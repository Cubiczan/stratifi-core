"""Board reporting generator with CHP hardening and PPTX export."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from cme.chp.models import DecisionCase, Dossier, FoundationAttack, FoundationDisclosure


@dataclass
class BoardMetric:
    name: str
    actual: float
    plan: float
    prior: float
    unit: str
    commentary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MetricTrend:
    name: str
    labels: List[str]
    actual: List[float]
    plan: List[float]
    unit: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BoardReportInput:
    company_name: str
    quarter_label: str
    board_meeting_date: str
    business_model: str
    goals: List[str]
    financial_highlights: List[BoardMetric]
    trend_series: List[MetricTrend]
    top_drivers: List[str]
    top_risks: List[str]
    top_actions: List[str]
    strategic_updates: List[str]
    outlook: List[str]
    leadership_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company_name": self.company_name,
            "quarter_label": self.quarter_label,
            "board_meeting_date": self.board_meeting_date,
            "business_model": self.business_model,
            "goals": self.goals,
            "financial_highlights": [item.to_dict() for item in self.financial_highlights],
            "trend_series": [item.to_dict() for item in self.trend_series],
            "top_drivers": self.top_drivers,
            "top_risks": self.top_risks,
            "top_actions": self.top_actions,
            "strategic_updates": self.strategic_updates,
            "outlook": self.outlook,
            "leadership_notes": self.leadership_notes,
        }


@dataclass
class BoardReportResult:
    source: BoardReportInput
    executive_takeaway: str
    financial_highlights: List[str]
    strategic_narrative: List[str]
    risk_narrative: List[str]
    action_narrative: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "executive_takeaway": self.executive_takeaway,
            "financial_highlights": self.financial_highlights,
            "strategic_narrative": self.strategic_narrative,
            "risk_narrative": self.risk_narrative,
            "action_narrative": self.action_narrative,
        }


def load_board_report_input(path: str | Path) -> BoardReportInput:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return BoardReportInput(
        company_name=payload["company_name"],
        quarter_label=payload["quarter_label"],
        board_meeting_date=payload["board_meeting_date"],
        business_model=payload["business_model"],
        goals=list(payload.get("goals", [])),
        financial_highlights=[BoardMetric(**item) for item in payload.get("financial_highlights", [])],
        trend_series=[MetricTrend(**item) for item in payload.get("trend_series", [])],
        top_drivers=list(payload.get("top_drivers", [])),
        top_risks=list(payload.get("top_risks", [])),
        top_actions=list(payload.get("top_actions", [])),
        strategic_updates=list(payload.get("strategic_updates", [])),
        outlook=list(payload.get("outlook", [])),
        leadership_notes=list(payload.get("leadership_notes", [])),
    )


def build_board_report(payload: BoardReportInput) -> BoardReportResult:
    strongest_metric = max(payload.financial_highlights, key=lambda item: _variance_pct(item.actual, item.plan), default=None)
    weakest_metric = min(payload.financial_highlights, key=lambda item: _variance_pct(item.actual, item.plan), default=None)
    takeaway = (
        f"{payload.company_name} enters the {payload.quarter_label} board meeting with "
        f"{_metric_phrase(strongest_metric)} offset by {_metric_phrase(weakest_metric)}."
        if strongest_metric and weakest_metric
        else f"{payload.company_name} enters the {payload.quarter_label} board meeting with a focused set of financial and strategic tradeoffs."
    )
    highlights = [_format_metric_highlight(metric) for metric in payload.financial_highlights[:5]]
    strategic_narrative = [
        f"{item} This matters because it ties directly to board priority execution."
        for item in payload.strategic_updates[:4]
    ]
    risk_narrative = [
        f"{item} The board should understand the trigger, owner, and mitigation timeline."
        for item in payload.top_risks[:3]
    ]
    action_narrative = [
        f"{item} Management should report progress against this action in the next board cycle."
        for item in payload.top_actions[:3]
    ]
    return BoardReportResult(
        source=payload,
        executive_takeaway=takeaway,
        financial_highlights=highlights,
        strategic_narrative=strategic_narrative,
        risk_narrative=risk_narrative,
        action_narrative=action_narrative,
    )


def build_board_reporting_case(
    result: BoardReportResult,
    *,
    owner: str = "cfo",
    origin_system: str = "Claude",
    origin_model: str = "GPT-5.4",
    partner_system: str = "Partner",
    partner_model: str = "GPT-5-equivalent",
) -> tuple[DecisionCase, FoundationDisclosure, FoundationAttack]:
    negative_metrics = [metric for metric in result.source.financial_highlights if metric.actual < metric.plan]
    dossier = Dossier(
        core_problem=f"Prepare a board-ready reporting package for {result.source.company_name} that ties financial performance to strategic meaning.",
        goal_state=[
            "Board materials highlight the few facts that matter most",
            "Drivers, risks, and actions align to one consistent management story",
            "Outlook is explicit about what could change the plan",
        ],
        current_state=[
            f"Quarter under review: {result.source.quarter_label}",
            f"Metrics in packet: {len(result.source.financial_highlights)}",
            f"Downside metrics versus plan: {len(negative_metrics)}",
        ],
        prior_decisions=[],
        constraints=[
            "Board output must be concise and decision-oriented",
            "Actual, plan, and prior-period framing must stay consistent",
            "Narrative should explain the so-what behind each major figure",
        ],
        unknowns=[
            "Board concern areas may shift relative to the prior meeting",
            "Some mitigation plans may still depend on non-finance teams",
        ],
        scope=[
            "Financial highlights",
            "Strategic updates",
            "Risks and actions",
            "Board deck packaging",
        ],
        origin_direction=[
            "Lead with bold takeaway, then evidence",
            "Keep every major metric connected to a decision or risk implication",
        ],
        structural_vulnerabilities=[
            "Narrative can become too optimistic if weak metrics are not translated into actions",
            "Board trust can erode if management uses inconsistent metric definitions across sections",
        ],
    )
    case = DecisionCase(
        decision_id=f"board-{result.source.company_name.lower().replace(' ', '-')}-{result.source.quarter_label.lower().replace(' ', '-')}",
        title=f"Board reporting package for {result.source.company_name} {result.source.quarter_label}",
        domain="board_reporting",
        created_at=datetime.now(timezone.utc).isoformat(),
        owner=owner,
        high_stakes=True,
        origin_system=origin_system,
        origin_model=origin_model,
        partner_system=partner_system,
        partner_model=partner_model,
        dossier=dossier,
    )
    disclosure = FoundationDisclosure(
        weakest_assumptions=[
            "The chosen headline metrics represent the most important board concerns",
            "Management commentary is specific enough to support board trust",
            "The outlook is balanced rather than overly defensive or promotional",
        ],
        invalidation_conditions=[
            "Key metric definitions differ from prior board materials or internal operating reviews",
            "The action plan does not clearly address the drivers behind weak performance",
        ],
        key_vulnerability="The package is most fragile where storytelling outruns the evidence behind weak or mixed results.",
    )
    score = 86 - min(12, len(negative_metrics) * 2)
    attack = FoundationAttack(
        assumption_attacks=[
            "Headline metrics may be accurate but still miss the board's real concern if the story is too finance-centric.",
            "Management commentary can sound polished while leaving open questions on accountability or timing.",
            "A strong executive summary can hide whether mitigation actions truly match the underlying drivers.",
        ],
        invalidation_exploitation=[
            "If definitions drift between materials, the board may challenge the credibility of the whole packet.",
            "If actions are generic, weak metrics will read as unmanaged risk rather than a controlled issue.",
        ],
        vulnerability_strike="The deck works only if every confident statement is anchored to a number, a driver, and a management action.",
        foundation_score=max(62, min(92, score)),
        attack_summary="The package is directionally board-ready, but it must earn credibility through consistent definitions and explicit management action on weak areas.",
    )
    dossier.foundation_score = attack.foundation_score
    dossier.prior_round_summary = [f"Negative metrics vs plan: {len(negative_metrics)}"]
    return case, disclosure, attack


def render_board_report_markdown(result: BoardReportResult) -> str:
    lines = [
        "# Board Reporting Generator",
        f"**Company:** {result.source.company_name}",
        f"**Quarter:** {result.source.quarter_label}",
        f"**Meeting Date:** {result.source.board_meeting_date}",
        "",
        "## Executive Takeaway",
        result.executive_takeaway,
        "",
        "## Financial Highlights",
    ]
    lines.extend(f"- {item}" for item in result.financial_highlights)
    lines.extend(["", "## Strategic Narrative"])
    lines.extend(f"- {item}" for item in result.strategic_narrative)
    lines.extend(["", "## Risks"])
    lines.extend(f"- {item}" for item in result.risk_narrative)
    lines.extend(["", "## Actions"])
    lines.extend(f"- {item}" for item in result.action_narrative)
    return "\n".join(lines)


def export_board_report_pptx(
    result: BoardReportResult,
    *,
    session_summary: str,
    output_path: str | Path,
) -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    builder_path = repo_root / "tools" / "build_board_report_deck.mjs"
    node_path = _resolve_node_path()
    _ensure_node_modules_link(repo_root)
    payload = {
        "report": result.to_dict(),
        "session_summary": session_summary,
    }
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        temp_json = Path(handle.name)
    try:
        subprocess.run(
            [node_path, str(builder_path), str(temp_json), str(output_file)],
            check=True,
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr or exc.stdout or "Board deck export failed.") from exc
    finally:
        temp_json.unlink(missing_ok=True)
    return output_file


def validate_pptx(path: str | Path) -> bool:
    with zipfile.ZipFile(path) as archive:
        return "ppt/presentation.xml" in set(archive.namelist())


def _format_metric_highlight(metric: BoardMetric) -> str:
    delta_pct = _variance_pct(metric.actual, metric.plan)
    qoq_pct = _variance_pct(metric.actual, metric.prior)
    return (
        f"{metric.name}: actual {_fmt(metric.actual, metric.unit)} versus plan {_fmt(metric.plan, metric.unit)} "
        f"({delta_pct:+.1f}%), versus prior {_fmt(metric.prior, metric.unit)} ({qoq_pct:+.1f}%). {metric.commentary}".strip()
    )


def _metric_phrase(metric: BoardMetric | None) -> str:
    if metric is None:
        return "a mixed operating picture"
    return f"{metric.name.lower()} at {_fmt(metric.actual, metric.unit)}"


def _fmt(value: float, unit: str) -> str:
    if unit == "pct":
        return f"{value:.1%}"
    if unit == "usd_m":
        return f"${value:,.1f}M"
    if unit == "months":
        return f"{value:.1f} months"
    return f"{value:,.1f}"


def _variance_pct(actual: float, base: float) -> float:
    if base == 0:
        return 0.0
    return ((actual - base) / abs(base)) * 100.0


def _ensure_node_modules_link(repo_root: Path) -> None:
    bundled_node_modules = Path(
        "/Users/cubiczan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
    )
    target = repo_root / "node_modules"
    if target.exists() or target.is_symlink():
        return
    target.symlink_to(bundled_node_modules, target_is_directory=True)


def _resolve_node_path() -> str:
    bundled = "/Users/cubiczan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    if os.path.exists(bundled):
        return bundled
    discovered = shutil.which("node")
    if discovered:
        return discovered
    raise RuntimeError("Node.js runtime not found for board deck export.")
