# Cognitive Mesh Enterprise Orchestrator


## Demo

https://github.com/user-attachments/assets/demo.mp4

> _Generated with [demo-video-generator](https://github.com/zan-maker/demo-video-generator)_
> Developer and enterprise infrastructure for building multi-agent AI systems that share deep organizational context and produce human-auditable, executable workflows.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-7%20passing-brightgreen)](tests/)

---

## What this is

As organizations deploy multiple specialized AI agents (a finance agent, a strategy agent, a compliance agent, …), they hit three predictable failures:

1. **Context fragmentation** — each agent sees a different slice of the organization
2. **Reasoning opacity** — humans get a conclusion without seeing how it was reached
3. **Output drift** — agents produce prose; humans need something runnable

The Cognitive Mesh Enterprise Orchestrator composes four well-specified subsystems to solve all three:

| Subsystem | Role | Spec it implements |
|---|---|---|
| **Cognitive Mesh Protocol** | Structured expansion ↔ compression reasoning with grounding checks | `cognitive-mesh-protocol.skill` |
| **Context Engineering Framework** | Layered short/long-term memory + entity/event/task schema | `context-engineering-framework.skill` |
| **Agentic Context Engineering** | Evolving playbooks with Generator/Reflector/Curator, delta-only updates | `agentic-context-engineering.skill` |
| *Statement & workflow synthesizer* | Turns multi-agent output into a vivid problem statement + executable workflow | *(bundled)* |

Together they form a **mesh**: every agent reads from and writes to shared context, reasons visibly, and self-improves its playbook after every turn.

---

## Quick start

```bash
git clone https://github.com/zan-maker/cognitive-mesh-orchestrator.git
cd cognitive-mesh-orchestrator
pip install -e .
cme demo
```

Or without installing:

```bash
PYTHONPATH=src python3 -m cme.cli demo
```

Both produce a full Markdown orchestration report: problem classification, per-agent reasoning traces, grounding verdicts, playbook deltas, and a final executable workflow.

---

## Announcing CHP

This repo now includes an early **Consensus Hardening Protocol (CHP)** workflow for capital allocation decisions.

CHP is the start of a new layer on top of the existing mesh:

- turn a finance decision into a structured session instead of a one-shot answer
- make assumptions, vulnerabilities, and lock states explicit
- require a partner response and third-party validation before a decision is considered hardened

In the current scaffold, CHP covers:

- session start with a normalized capital allocation dossier
- context check and model parity assessment
- R0 and foundation-stage evaluation
- partner packet ingestion
- third-party validation with `PROVISIONAL_LOCK -> LOCKED` progression

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
```

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
cognitive-mesh-orchestrator/
├── src/
│   ├── cme/                       # Core framework
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
│   └── basic_demo.py              # Minimal end-to-end example
├── tests/
│   └── test_mesh.py               # Full pipeline smoke tests (7, all passing)
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

cme chp-start                  # Start a CHP capital allocation session scaffold
cme chp-receive                # Attach a partner packet to an existing CHP decision
cme chp-validate               # Apply third-party validation to a CHP decision
```

---

## Tests

```bash
pip install pytest
PYTHONPATH=src pytest tests/ -v
```

All 7 tests pass, covering protocol rendering, hallucination-risk heuristics, playbook dedup/refinement, context selection, statement completeness, and an end-to-end orchestration that verifies topological ordering between finance → strategy → compliance.

---

## License

MIT. See [LICENSE](LICENSE).
