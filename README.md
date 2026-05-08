# Consensus Hardening Protocol


## Demo

https://github.com/user-attachments/assets/demo.mp4

> _Generated with [demo-video-generator](https://github.com/zan-maker/demo-video-generator)_
> Developer and enterprise infrastructure for building hardened, human-auditable multi-agent finance and decision workflows.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-42%20passing-brightgreen)](tests/)

---

## What this is

As organizations deploy multiple specialized AI agents (a finance agent, a strategy agent, a compliance agent, …), they hit three predictable failures:

1. **Context fragmentation** — each agent sees a different slice of the organization
2. **Reasoning opacity** — humans get a conclusion without seeing how it was reached
3. **Output drift** — agents produce prose; humans need something runnable

Consensus Hardening Protocol composes five well-specified subsystems to solve all three:

| Subsystem | Role | Spec it implements |
|---|---|---|
| **Consensus Hardening Protocol** | Cross-model decision hardening with gates, packets, lock states, adversarial foundation attack, VCL diagnosis, and third-party validation | `cme.chp` |
| **Cognitive Mesh Protocol** | Structured expansion ↔ compression reasoning with grounding checks | `cognitive-mesh-protocol.skill` |
| **Context Engineering Framework** | Layered short/long-term memory + entity/event/task schema | `context-engineering-framework.skill` |
| **Agentic Context Engineering** | Evolving playbooks with Generator/Reflector/Curator, delta-only updates | `agentic-context-engineering.skill` |
| *Statement & workflow synthesizer* | Turns multi-agent output into a vivid problem statement + executable workflow | *(bundled)* |

Together they form a hardened decision system: every agent reads from and writes to shared context, reasons visibly, and improves its operating playbook over time.

---

## Quick start

```bash
git clone https://github.com/zan-maker/consensus-hardening-protocol.git
cd consensus-hardening-protocol
pip install -e .
cme demo
```

Or without installing:

```bash
PYTHONPATH=src python3 -m cme.cli demo
```

Both produce a full Markdown orchestration report: problem classification, per-agent reasoning traces, grounding verdicts, playbook deltas, and a final executable workflow.

---

## Consensus Hardening Protocol

CHP is the decision-governance layer for origin-agnostic, cross-model finance workflows. It is designed for high-stakes CFO decisions where a single model answer is not good enough: the system records the foundation, attacks it, packages it for a partner model, requires echoed payload integrity, and prevents final lock until third-party validation.

The current implementation covers:

- pre-session context checks with duplicate halt and related-lock auto-population
- model parity checks that halt on significant asymmetry
- R0 gate and foundation score gate before packet generation
- adversarial foundation disclosure and foundation attack
- Phase 0 devil's advocate capture and Round 3 implementation devil's advocate support
- VCL diagnosis in the origin packet
- `BEGIN_PAYLOAD` / `END_PAYLOAD` packet envelopes with required `PAYLOAD_ECHO`
- structured `STATE_SNAPSHOT` persistence
- Phase 1 gate enforcement before implementation rounds
- Round 5 `PROVISIONAL -> UNRESOLVED` forcing
- `PROVISIONAL_LOCK -> LOCKED` progression only after third-party validation
- strict origin 3-section contract checks
- structured partner packet primitives for item agreements, scoring tables, flip criteria, and state snapshots
- single-winner scoring validation, ASCII-only packet checks, verification checklist runner, and max-5-round enforcement
- council-spawn and convergence-closure primitives for high-stakes low-confidence sessions
- standalone `TriangulationRunner` adversary/fact-check pass
- `AdversaryMeshAgent` wrapper for plugging the adversary into mesh orchestration
- mandatory `FinancialAnalysisGuard` for finance CLI workflows
- CFO accuracy policy that demotes unresolved finance outputs to `REQUIRES_HUMAN_VERIFICATION`

The core state model lives in [`src/cme/chp`](src/cme/chp). The CFO operating layer that uses it with finance, strategy, and compliance agents lives in [`src/cme/cfo_os`](src/cme/cfo_os).

Current remaining protocol work:

- raw text parser for converting partner 7-section packets into the structured packet model
- multi-model council execution beyond the current council-spawn primitive
- hosted session URL exchange and release-grade closure reporting around the current convergence-closure primitive

Quick run:

```bash
PYTHONPATH=src python3 -m cme.cli chp-start \
  --title "Fund enterprise workflow" \
  --company "Acme" \
  --problem "Should we fund a new enterprise workflow team this quarter?" \
  --amount 2500000 \
  --payback-months 14 \
  --min-runway 12 \
  --current-runway 18
```

Full demo package:

- [CHP_DEMO_VIDEO.md](CHP_DEMO_VIDEO.md)
- [docs/CHP_FINANCE_PROJECT_ROADMAP.md](docs/CHP_FINANCE_PROJECT_ROADMAP.md)
- [examples/chp_demo_video.sh](examples/chp_demo_video.sh)
- [examples/chp_demo_partner_packet.txt](examples/chp_demo_partner_packet.txt)
- [RELEASE_NOTES_CHP.md](RELEASE_NOTES_CHP.md)
- [docs/media/README.md](docs/media/README.md)

This flow shows a decision moving from session start to partner packet ingestion to third-party validation and final lock.

Once recorded, the intended video path is:

- `docs/media/chp-demo.mp4`

Current CHP CLI commands:

```bash
PYTHONPATH=src python3 -m cme.cli chp-start
PYTHONPATH=src python3 -m cme.cli chp-receive
PYTHONPATH=src python3 -m cme.cli chp-validate
PYTHONPATH=src python3 -m cme.cli chp-triangulate --claim "EBITDA improves by 20%"
```

---

## CFO Workflow Suite

CHP now ships with a CFO workflow suite. Each workflow creates a finance artifact and attaches a CHP session so the output is auditable before it becomes a decision record.

For finance workflows, the policy is mandatory: every CLI analysis runs CHP and then spawns the `TriangulationRunner` adversary pass. Because CFO-grade work has a 100% verification floor, any foundation score below `100`, any open structural vulnerability, or any open blind spot blocks final lock and marks the case `REQUIRES_HUMAN_VERIFICATION`.

| Workflow | CLI command | Output artifacts |
|---|---|---|
| Monthly CFO Variance Studio | `variance-studio` | Markdown, JSON, HTML |
| 13-Week Cash Forecast Engine | `cash-forecast-13w` | Markdown, JSON, Excel workbook |
| 24-Month SaaS Operating Model | `saas-model-24m` | Markdown, JSON, Excel workbook |
| Board Reporting Generator | `board-reporting-generator` | Markdown, JSON, PowerPoint deck |
| AP Cash & Payables Optimizer | `ap-optimizer` | Markdown, JSON, Excel workbook |
| CFO Decision Impact Simulator | `decision-impact-simulator` | Markdown, JSON, HTML |
| SaaS KPI Dashboard | `saas-kpi-dashboard` | Markdown, JSON, HTML, Excel workbook |
| Investment Committee Scoring Tool | `investment-committee` | Markdown, JSON, Excel workbook |
| Multi-Agent CFO Operating System | `cfo-os` | CFO session report with mesh trace, audit trail, and CHP state |

The finance roadmap is documented in [docs/CHP_FINANCE_PROJECT_ROADMAP.md](docs/CHP_FINANCE_PROJECT_ROADMAP.md).

---

## The 90-second demo

```bash
cme demo "Should we invest $4M in a new enterprise tier next quarter, \
          or extend SMB to cover enterprise use cases?"
```

What you'll see:

1. **Finance agent** runs first (no upstream dependencies). Expansion cycle across 6 steps — reframe, constraints, alternatives, assumptions, edge cases, cross-domain analogy — then compresses to `phased spend, 60/40 gated, 14-month payback`. Playbook gains a rule.
2. **Strategy agent** reads finance's recommendation from shared context automatically. Recommends `core anchor + 15% adjacent-market experiment`, flags what would falsify it. Existing playbook bullet gets marked `helpful`.
3. **Compliance agent** reads both upstream recommendations, produces `conditional approval` with DPIA + SCC + gated review tied to the finance milestone.
4. The synthesizer produces:
   - A **Statement** with 5 Whys, consequences across strategic/cultural/financial axes, and a strategic connection
   - An **executable Workflow** of 3 typed steps with correctly inferred `depends_on` ordering (topologically sorted from the agents' `produces`/`consumes` capabilities)

Every claim in the report traces back to an agent's expansion step, which traces back to a shared-context entity.

See [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) for the full walkthrough, recommended talking points, and expected output.

---

## Architecture

```
                        ┌──────────────────────────┐
   ┌───── shared ──────▶│   Context Engine         │◀───── shared ─────┐
   │                    │   (entities/events/tasks │                   │
   │                    │    + short/long memory)  │                   │
   │                    └──────────────────────────┘                   │
   ▼                                                                    ▼
┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│ Finance Agent      │     │ Strategy Agent     │     │ Compliance Agent   │
│  ├─ Playbook (ACE) │     │  ├─ Playbook (ACE) │     │  ├─ Playbook (ACE) │
│  └─ Protocol (CMP) │     │  └─ Protocol (CMP) │     │  └─ Protocol (CMP) │
└──────────┬─────────┘     └──────────┬─────────┘     └──────────┬─────────┘
           │ produces                 │ consumes+produces        │ consumes
           ▼                          ▼                          ▼
      budget_envelope        market_positioning            risk_register
      roi_model              go_to_market                  mitigations
           │                          │                          │
           └──────────────┬───────────┴──────────────┬───────────┘
                          ▼                          ▼
                 ┌──────────────────────────────────────────┐
                 │  EnterpriseOrchestrator                  │
                 │    - topologically sorts agents          │
                 │    - routes each turn through Protocol   │
                 │    - collects outputs                    │
                 │    - emits Statement + Workflow          │
                 └──────────────────────────────────────────┘
```

### Cognitive Mesh Protocol (`cme.protocol`)

Every agent turn runs through a visible breathing cycle:

- **Expansion** (up to 6 steps): Reframe → Constraints → Alternatives → Assumptions → Edge cases → Cross-domain analogy. Each step can carry explicit `uncertainty_flags`.
- **Compression** (1–2 steps): Integrate → Commit.
- **Grounding check**: every claim is tagged `verified | inferred | pattern-match` with a confidence level. A `detect_hallucination_risk` heuristic flags unsourced authority phrases ("studies show …") and bare percentages.
- **Failure-mode detection**: `FOSSIL_STATE` (repetition), `CHAOS_STATE` (expansion without compression), `HALLUCINATION_RISK` (≥3 ungrounded claims).
- **Adaptive classification**: strategic / analytical / creative / technical — auto-detected from the problem text, calibrates cycle depth.

### Context Engine (`cme.context`)

Implements the Context Engineering Framework:

- **Layered memory**: short-term with TTL + temporal weighting, auto-promotion to long-term based on importance + access frequency.
- **Fixed-schema self-baking**: `Entity { id, type, attributes }` / `Event { timestamp, actor, action, object }` / `Task { id, goal, subtasks, owner }`.
- **Context selection** by combined score (semantic relevance 50% + recency 20% + importance 20% + frequency 10%), with ≥0.85 cosine dedup.
- **Structured messages** for inter-agent sharing — each agent receives a `snapshot_for(agent_name, query)` packet containing the entities, recent events, active tasks, and top-k relevant notes.
- Thread-safe so agents can run concurrently.

No embedding model dependency — uses deterministic lexical cosine so the demo runs offline. Swap `_score_relevance` for a real embedding call in production.

### Agentic Context Engineering (`cme.playbook`)

Each agent owns a **playbook**, not a prompt:

- Bullets are `{id, section, content, helpful, harmful}`
- Six sections: `strategies_and_hard_rules`, `useful_code_snippets`, `troubleshooting_and_pitfalls`, `apis_to_use_for_specific_information`, `verification_checklist`, `domain_concepts`
- **Delta-only updates**: `ADD`, `INCREMENT`, `MERGE`, `PRUNE`. Full regeneration is impossible by design — this is how ACE prevents context collapse.
- **Reflector** analyzes each turn's trajectory + outcome + grounding issues → insights
- **Curator** transforms insights into deltas (never full rewrites)
- **Refinement pass** prunes low-utility bullets (`helpful/(helpful+harmful) < 0.4` after 3 samples) and dedupes by cosine similarity

The demo seeds each agent's playbook with 3 starter bullets per domain and extends it on every turn.

### Statement & workflow synthesizer (`cme.bridge`)

After every agent has contributed, the synthesizer produces:

1. A **Statement** with an entry point (problem / opportunity / situation), observable tension, 5 Whys derived from each agent's reframe step, consequences (strategic / cultural / financial) with a timeline, and a strategic connection to the organization's mission.
2. A **Workflow**: each agent's recommendation becomes a typed `WorkflowStep` with `inputs` / `outputs` / `depends_on`. Dependency inference is automatic — steps that consume `budget_envelope` are ordered after the step that produces it.
3. A **completeness report** for the statement against a 5-point checklist.

---

## Repository layout

```
consensus-hardening-protocol/
├── src/
│   ├── cme/                       # Core framework
│   │   ├── chp/                   # Consensus Hardening Protocol
│   │   ├── cfo_os/                # Multi-Agent CFO Operating System
│   │   ├── finance/               # CFO workflow engines and artifacts
│   │   ├── protocol.py            # Cognitive Mesh Protocol
│   │   ├── context.py             # Context Engine (memory + schema)
│   │   ├── playbook.py            # ACE playbook + Reflector + Curator
│   │   ├── bridge.py              # Statement + Workflow synthesizer
│   │   ├── agent.py               # MeshAgent base class
│   │   ├── orchestrator.py        # EnterpriseOrchestrator
│   │   └── cli.py                 # `cme` command-line tool
│   └── demo/                      # Shipped example agents
│       ├── finance_agent.py
│       ├── strategy_agent.py
│       └── compliance_agent.py
├── examples/
│   ├── basic_demo.py              # Minimal end-to-end example
│   └── *.csv / *.json             # Finance workflow sample inputs
├── tests/
│   ├── test_mesh.py               # Core orchestration smoke tests
│   └── test_*                     # CHP, CFO OS, finance workflow tests
├── DEMO_SCRIPT.md                 # Written demo script with talking points
├── pyproject.toml
└── README.md
```

---

## Building your own agent

```python
from cme.agent import AgentCapability, MeshAgent
from cme.protocol import CompressionStep, ConfidenceLevel, ExpansionStep

class LegalAgent(MeshAgent):
    def __init__(self):
        super().__init__(
            name="legal",
            capability=AgentCapability(
                domain="legal",
                produces=["contract_terms"],
                consumes=["risk_register"],
            ),
        )

    def expand(self, problem, context):
        return [
            ExpansionStep(label="Reframe", content="..."),
            ExpansionStep(label="Constraints", content="..."),
            # ...up to 6 steps
        ]

    def compress(self, problem, expansion, context):
        return (
            "final recommendation...",
            [CompressionStep(label="Integrate", content="...")],
            ConfidenceLevel.MEDIUM,
            "what would change this recommendation",
            {"contract_terms": {...}},  # structured output
        )
```

Drop the agent into `EnterpriseOrchestrator(agents=[...])` — the orchestrator discovers its `produces`/`consumes` capability and places it in the execution order automatically.

### Plugging in a real LLM

The framework is LLM-agnostic. Each agent's `expand` and `compress` are plain methods — call any model inside them. The protocol handles grounding checks, failure modes, playbook updates, and rendering regardless of what produces the reasoning.

---

## CLI reference

```bash
cme demo [PROBLEM]             # Run the full orchestration on a problem
  --entry-point {problem,opportunity,situation}
  --title TITLE                # Workflow title
  --json                       # JSON output instead of Markdown
  --out FILE                   # Also write Markdown report to FILE

cme playbook {finance,strategy,compliance}   # Show an agent's seeded playbook
  --json

cme context                    # Dump the seeded organizational context

cme chp-start                  # Start a CHP capital allocation session
cme chp-receive                # Attach a partner packet to an existing CHP decision
cme chp-validate               # Apply third-party validation to a CHP decision
cme chp-triangulate            # Standalone adversary/fact-check pass for a claim

cme variance-studio            # Monthly actual-vs-budget variance analysis
cme cash-forecast-13w          # 13-week cash forecast
cme cash-forecast-13w-template # Excel input template for the cash forecast
cme saas-model-24m             # 24-month SaaS operating model
cme board-reporting-generator  # Board-ready reporting package and PPTX
cme ap-optimizer               # AP cash and payables optimizer
cme decision-impact-simulator  # CFO scenario simulator
cme saas-kpi-dashboard         # SaaS KPI actual-vs-budget dashboard
cme investment-committee       # Investment committee scoring tool
cme cfo-os                     # Multi-agent CFO operating session
```

---

## Tests

```bash
pip install pytest
PYTHONPATH=src pytest tests/ -v
```

The focused suite currently has 42 passing tests covering protocol rendering, payload integrity, gate enforcement, lock progression, context reuse, strict packet contracts, the adversary runner, CFO accuracy guard, CFO OS behavior, workbook/deck exporters, and the finance workflow engines.

---

## License

MIT. See [LICENSE](LICENSE).
# stratifi-core
