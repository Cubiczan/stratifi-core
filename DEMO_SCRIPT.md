# Demo Script — Cognitive Mesh Enterprise Orchestrator

Target length: **8 minutes**. Audience: technical founders, platform engineers, or enterprise AI leads who are already wrangling multiple specialized agents and running into coordination failures.

Everything in this script is runnable locally — no API keys, no network calls. The demo agents are deterministic so the output is reproducible across takes.

---

## 0. Setup (before recording)

```bash
git clone https://github.com/zan-maker/cognitive-mesh-orchestrator.git
cd cognitive-mesh-orchestrator
pip install -e .
pip install pytest
PYTHONPATH=src pytest tests/ -v   # 7 passing — good baseline
```

Have two terminal panes ready:
- **Pane A** (big): for running `cme` commands
- **Pane B** (small): for showing files with a code viewer

---

## 1. The problem (0:00 – 0:45)

**Say this:**

> When an organization goes from one AI agent to five, three things break.
>
> First, each agent ends up with its own slice of organizational context. The finance agent knows the budget; the strategy agent knows the competitive map; nobody sees the whole picture.
>
> Second, you get answers without reasoning. A single confident paragraph. If it's wrong, you can't tell why it's wrong until it's too late.
>
> Third, the output is prose — but the thing you actually need is *runnable*. A workflow. Owners, inputs, outputs, dependencies.
>
> The Cognitive Mesh Enterprise Orchestrator fixes all three by composing four well-specified subsystems into one mesh. Let me show you.

---

## 2. Show the architecture (0:45 – 1:30)

**Pane B** — open `README.md` and scroll to the architecture diagram.

**Say this, pointing at each piece:**

> Shared Context Engine in the middle — layered memory, entity/event/task schema, thread-safe.
>
> Each agent on the outside has two things: its own evolving playbook, and a reasoning protocol that forces expansion-then-compression with grounding checks.
>
> Agents declare what they `produce` and `consume`. The orchestrator topologically sorts them. Everything else composes.

---

## 3. Run the demo (1:30 – 3:00)

**Pane A:**

```bash
cme demo "Should we invest $4M in a new enterprise tier next quarter, \
          or extend SMB to cover enterprise use cases?"
```

**As the output scrolls, narrate:**

> Three agents ran: finance, then strategy, then compliance. Topological sort, not a hard-coded pipeline — if I added a legal agent that consumes `contract_terms`, the orchestrator would place it automatically.
>
> Each agent's turn has the same shape. Problem classification — strategic, analytical, creative, or technical — auto-detected. Then the expansion cycle: reframe, constraints, alternatives, assumptions, edge cases, cross-domain analogy. Then compression — integrate, commit. Every uncertain claim is flagged inline. Every grounding check says whether the claim is verified, inferred, or pattern-matched.
>
> Notice strategy's reasoning — it cites the finance recommendation verbatim. That's not a prompt chain. The orchestrator passed finance's output into shared context; strategy pulled it back out during its own context-selection pass.

---

## 4. Show the playbook evolving (3:00 – 4:15)

**Pane A:**

```bash
cme playbook strategy
```

**Say this:**

> This is the strategy agent's playbook — evolved from a 3-bullet seed. Structured bullets with `helpful`/`harmful` counters. The Reflector analyzes each turn's trajectory against the outcome; the Curator emits delta operations — add, increment, merge, prune. Never a full rewrite. That's how this system avoids context collapse, which is the failure mode where an LLM tasked with rewriting a context shrinks it into a summary and loses accumulated knowledge.

Scroll back up in Pane A to the "Playbook Deltas" block from the demo run.

**Say this, pointing:**

> Here — `INC chk-00001 helpful -> h=3/x=0`. That's the checklist rule "does the recommendation survive the 'competitor mirrors us next quarter' test" — the reflector detected the agent *used* that rule in its reasoning, so the counter went up. Bullets that consistently go unused, or get tagged harmful, get pruned on the next refinement pass.

---

## 5. Show context sharing in action (4:15 – 5:15)

**Pane A:**

```bash
cme context
```

**Say this:**

> This is the organizational context the agents see. Entities like `Aperture Corp`, `Finance Ops`, `metric:Net Dollar Retention`, `policy:Regulatory reserve ratio`. Events get appended as agents act. Tasks track in-progress goals.
>
> During the demo run, finance wrote its recommendation into shared context with importance 0.85, which promoted it straight to long-term memory. Strategy's `snapshot_for("strategy", problem)` call pulled it back out scored by semantic relevance plus recency plus importance. The orchestrator never explicitly piped output A into prompt B — the context engine did the routing.

---

## 6. Show the executable workflow (5:15 – 6:30)

**Pane A** — scroll to the end of the demo output.

**Say this:**

> This is the payoff. The mesh doesn't just produce three recommendations — it produces a **Statement** and a **Workflow**.
>
> The Statement has observable tension, 5 Whys derived from each agent's reframe step, consequences broken into strategic / cultural / financial axes, and a strategic connection to the organization's mission. That's five checklist items a human can audit.
>
> The Workflow is three typed steps. Each has owner, inputs, outputs, and `depends_on`. S02 depends on S01 because strategy consumes `budget_envelope` and finance produces it — inferred from the capability declarations, not hard-coded. Pipe this into Temporal, Airflow, or a plain cron job and it runs.

---

## 7. Show the failure-mode detection (6:30 – 7:15)

**Pane B** — open `src/cme/protocol.py` and jump to `detect_failure_mode`.

**Say this:**

> Three failure modes, detected automatically:
>
> **Fossil State** — the agent keeps restating the same idea with different words. Detected by looking at the 40-char prefix of each expansion step.
>
> **Chaos State** — wide expansion, no compression. Tons of ideas, no commitment.
>
> **Hallucination Risk** — three or more ungrounded claims. The grounding check runs a heuristic for unsourced authority phrases like "studies show" or bare percentages without a stated source.
>
> When any of these fire, the result includes a `handoff_note` with a warning prefix, so a downstream agent — or a human — can choose not to act on it.

---

## 8. The `so what` close (7:15 – 8:00)

**Say this:**

> Three takeaways.
>
> One — multi-agent systems fail because *context* fails. Solve context first; agent quality follows.
>
> Two — reasoning has to be visible. Not just logged, visible — with grounding checks, uncertainty flags, and failure-mode detection a human can spot-check in seconds.
>
> Three — the output of a mesh is a workflow, not a paragraph. Typed, dependency-ordered, owner-attributed.
>
> The entire demo you just saw — 3 agents, shared context, evolving playbooks, grounding checks, executable workflow — is about 1,500 lines of Python with zero external dependencies. That's the whole point. Composable specs beat monolithic frameworks.
>
> Repo link is in the description. `cme demo` runs offline. Ship agents that survive a Monday-morning review.

---

## Appendix — Recovery commands if something goes sideways

```bash
# Agent showing empty output?
PYTHONPATH=src python3 -c "from demo import FinanceAgent; a = FinanceAgent(); print(a.playbook.render_for_generator())"

# Context engine misbehaving?
PYTHONPATH=src python3 -c "from cme.context import ContextEngine, Entity; c = ContextEngine(); c.upsert_entity(Entity(id='x', type='test')); print(c.dump_json())"

# Need a JSON dump for a slide?
cme demo --json | jq '.workflow'
```

## Appendix — Expected output summary (for on-screen text overlays)

| Moment | What viewers should see on screen |
|---|---|
| 1:45 | `**Problem:** Should we invest $4M...` header |
| 2:10 | "Expansion Cycle (count=1)" — 6 numbered steps |
| 2:40 | "Compression Cycle" — 2 numbered steps |
| 2:55 | "Grounding Check" — confidence tag visible |
| 3:30 | `[shr-xxxxx] helpful=N harmful=M :: ...` bullets |
| 4:30 | Entity map + tasks from `cme context` |
| 5:45 | "## Executable Steps" with S01/S02/S03 and `depends_on` arrows |
| 7:00 | `detect_failure_mode` source in Pane B |

## Appendix — One-paragraph elevator pitch

> Cognitive Mesh Enterprise Orchestrator is infrastructure for building multi-agent AI systems where every agent shares the same organizational context, reasons visibly through an expansion-compression cycle with grounding checks, maintains its own self-improving playbook, and where the combined output is not a paragraph but an executable, dependency-ordered workflow with a five-checklist-item strategic statement attached. It's 1,500 lines, zero external dependencies, LLM-agnostic, and runs offline.
