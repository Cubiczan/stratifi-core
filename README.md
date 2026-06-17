# Stratifi Core

> Cognitive Mesh Enterprise Orchestrator — multi-agent coordination for CFO-grade
> financial analysis, with consensus-hardened decision governance and an auditable
> trail from exploration to a locked recommendation.

Stratifi Core packages the Cognitive Mesh Enterprise Orchestrator (`cme`): a set of
finance engines (cash forecasting, variance analysis, SaaS operating models, board
reporting, AP optimization, investment-committee scoring) coordinated by multiple
agents and governed by the Consensus Hardening Protocol (CHP).

## Quick Start

```bash
# Clone the repository
git clone https://github.com/icohangar-ops/stratifi-core.git
cd stratifi-core

# Install dependencies
pip install -r requirements.txt

# Run the minimal end-to-end example
python examples/basic_demo.py
```

Installing the package (editable) also exposes the `cme` command-line entry point:

```bash
pip install -e ".[dev]"
cme demo
```

## Command-Line Interface

The `cme` CLI exposes the orchestrator and each finance engine as a subcommand:

| Command | Purpose |
|---------|---------|
| `cme demo` | Run an end-to-end orchestration on a sample problem |
| `cme playbook` | Show a seeded agent playbook |
| `cme context` | Dump the seeded organizational context |
| `cme chp-start` | Start a CHP capital-allocation session scaffold |
| `cme chp-receive` | Attach a partner packet to an existing CHP decision |
| `cme chp-validate` | Apply third-party validation to a CHP decision |
| `cme chp-triangulate` | Run a standalone CHP adversary/fact-check pass on a claim |
| `cme variance-studio` | Run the monthly CFO Variance Studio on a CSV file |
| `cme cash-forecast-13w` | Run the 13-week cash forecast engine on CSV inputs |
| `cme saas-model-24m` | Run the 24-month SaaS operating model |
| `cme board-reporting-generator` | Generate a board reporting package and PPTX deck |
| `cme ap-optimizer` | Run the AP Cash & Payables Optimizer |
| `cme decision-impact-simulator` | Run the CFO Decision Impact Simulator |
| `cme saas-kpi-dashboard` | Build the SaaS KPI dashboard from actuals and budget CSVs |
| `cme investment-committee` | Score a finance proposal for investment-committee review |

Run `cme <command> --help` for the arguments of any subcommand. Sample input files
live under `examples/` (CSV and JSON).

## Core Components

| Module | Purpose |
|--------|---------|
| `src/cme/orchestrator.py`, `src/cme/context.py` | Enterprise orchestrator and context engine |
| `src/cme/chp/` | Consensus Hardening Protocol: gates, foundation disclosure, adversary, validation |
| `src/cme/cfo_os/` | CFO operating system: briefs, dossiers, artifacts, audit trail |
| `src/cme/finance/` | Finance engines (cash, variance, SaaS model, board reporting, AP, simulator) |
| `src/cme/db/` | SQLAlchemy persistence layer (CockroachDB/PostgreSQL, SQLite for local dev) |
| `src/demo/` | Sample finance, strategy, and compliance agents used by the demos |

## Consensus Hardening Protocol

Recommendations pass through CHP before they are considered trustworthy:

- R0 gate: solvable, scoped, valid, worth it
- Foundation disclosure of the weakest assumptions
- Adversarial review (devil's advocate)
- Third-party validation (independent confirm/reject) before a decision locks

## Configuration

Database access is configured via environment variables. Copy `.env.example` to
`.env` and set values as needed:

- `STRATIFI_DATABASE_URL` — SQLAlchemy URL for CockroachDB/PostgreSQL. If unset,
  the app falls back to a local SQLite database for development.
- `STRATIFI_DB_CONNECT_TIMEOUT`, `STRATIFI_DB_STATEMENT_TIMEOUT_MS` — optional timeouts.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## Tech Stack

- Python 3.10+
- SQLAlchemy 2.x (CockroachDB / PostgreSQL via psycopg2; SQLite for local dev)
- cubiczan-resilience (retry/timeout primitives)

## License

MIT. See [LICENSE](LICENSE) for details.
