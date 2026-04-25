# CHP Finance Project Roadmap

## Purpose

This document translates the current finance opportunity set into a **CHP-hardened implementation roadmap**.

CHP matters here because these are not just analytics workflows. They are decision workflows where:

- assumptions should be surfaced before they are trusted
- partner critique should happen before narrative lock
- third-party validation should exist before final board or CFO use

## Ranking Method

Projects are ranked using:

- **ROI speed**: how quickly the workflow can generate finance value
- **Decision criticality**: how expensive false consensus would be
- **Data readiness**: how close the inputs already are to an MVP
- **CHP fit**: how naturally the workflow benefits from hardening, lock states, and validation

Scale:

- Effort: `Low`, `Medium`, `High`
- Impact: `Medium`, `High`, `Very High`
- CHP Fit: `Medium`, `High`, `Very High`

## Ranked Roadmap

| Rank | Project | Core CFO Use Case | Effort | Impact | CHP Fit | Required Data | Skills / Assets | Recommended MVP |
|---|---|---|---|---|---|---|---|---|
| 1 | Monthly CFO Variance Copilot | Explain actual vs budget performance, identify top drivers, produce board-ready commentary | Medium | Very High | Very High | Actuals, budget, account mapping, entity/department dimensions, prior month narrative | `Excel`, `CFO Monthly analysis prompt.docx`, `Variance AI app and AP Optimier app prompts.docx` | Upload two files, rank top 3 drivers, generate narrative, run CHP review before lock |
| 2 | 13-Week Cash Forecast Engine | Consolidate AR, AP, payroll, and outflows into a short-term cash view with red-zone detection | Medium | Very High | High | Opening cash, AR aging, AP schedule, payroll calendar, outflows, recent sales/receipts | `Excel`, `13 week forecast.docx`, `financial-risk-assessment-matrix.skill` | File upload, weekly summary, red-zone flags, scenario toggles, CHP hardening on assumptions and action plan |
| 3 | Board Reporting Generator | Produce repeatable board decks from finance data plus leadership commentary | High | Very High | Very High | P&L, cash, KPI tracker, variance report, strategic notes, board commentary | `PowerPoint`, `board-reporting-generator.skill`, `financial-storytelling.skill`, `Board storytelling.docx`, `board presentation.docx` | KPI ingestion, slide skeleton, chart build, leadership notes merge, CHP lock before board issue |
| 4 | AP Cash & Payables Optimizer | Prioritize weekly payments under cash constraints without damaging strategic suppliers | Medium | High | High | AP ledger, due dates, vendor metadata, strategic vendor flags, available cash | `Excel`, `Variance AI app and AP Optimier app prompts.docx` | Payment ranking UI, overdue protection, strategic vendor preference, CHP hardening on payout policy |
| 5 | 24-Month SaaS Operating Model | Build a forward operating model for MRR, headcount, burn, fundraising, and runway | High | Very High | High | Historical MRR, churn, ARPA, headcount, opex, fundraising assumptions | `Excel`, `24 month forecast.docx`, `SAAS Driver based MRR forecast.docx` | One-sheet or workbook model, editable drivers, cash runway chart, CHP review on assumptions |
| 6 | CFO Decision Impact Simulator | Show how decisions affect runway, growth, profitability, and resilience | Medium | High | High | Current finance snapshot, churn, customer growth, salary assumptions, AR/AP assumptions | `CFO Decision Impact Simulator.docx` | Lightweight web app with sliders and KPI tiles, CHP-backed recommendation summary |
| 7 | SaaS KPI Dashboard | Deployable dashboard for MRR, ARR, EBITDA, CAC, LTV, Rule of 40, and variance | Medium | High | Medium | Actual CSV, budget CSV, metric mapping | `Excel`, `SAAS Dashboard .docx` | Replaceable CSV ingestion, KPI cards, trend charts, CHP commentary on outliers |
| 8 | Investment Committee Scoring Tool | Score capex, acquisitions, software spend, and growth bets consistently | Medium | High | Very High | Investment memo, DCF assumptions, CAC/LTV assumptions, strategic rationale | `investment-evaluation-rubric.skill`, `DCF model prompt.docx`, `CAC LTV prompt.docx` | Structured scorecard, recommendation tier, CHP validation before committee output |
| 9 | SEC / Earnings / Company Research Workbench | Build reusable corp dev and treasury research packets on public companies | Medium | High | High | 10-K, 10-Q, 8-K, earnings calls, investor decks, peer data | `Company research.docx`, `SEC filing deep research prompt.docx`, `Top stock research prompt.docx` | Source-linked dossier, thesis builder, CHP challenge of unsupported conclusions |
| 10 | Multi-Agent CFO Operating System | Shared-context finance, strategy, and compliance workflow across major decisions | High | Extreme | Very High | Session history, prior decisions, KPI data, policy data, planning inputs | `README.md`, `cognitive-mesh-protocol.skill`, `context-engineering-framework.skill`, `agentic-context-engineering.skill`, orchestrator repo | CHP-driven operating layer with shared context, reusable locks, and auditable packet flow |

## Recommended Build Waves

### Wave 1: Fastest ROI

1. Monthly CFO Variance Copilot
2. 13-Week Cash Forecast Engine
3. Board Reporting Generator

Why this wave:

- clear data shape
- immediate finance team value
- visible outputs for CFO, CEO, and board
- strong CHP use because narrative lock matters

### Wave 2: Operating Control

4. AP Cash & Payables Optimizer
5. 24-Month SaaS Operating Model
6. CFO Decision Impact Simulator

Why this wave:

- extends from reporting into planning and cash control
- high day-to-day decision usefulness
- pushes CHP from narrative hardening into policy and scenario hardening

### Wave 3: Platform Expansion

7. SaaS KPI Dashboard
8. Investment Committee Scoring Tool
9. SEC / Earnings / Company Research Workbench
10. Multi-Agent CFO Operating System

Why this wave:

- broadens the surface area
- turns individual workflows into an integrated system
- creates the strongest long-term moat

## CHP Hardening Pattern by Project

All ten projects should use the same hardening pattern:

### Phase 0: Foundation

Purpose:

- identify weak assumptions
- surface invalidation conditions
- expose the key vulnerability

Examples:

- Variance Copilot: are the top drivers actually evidenced by the data?
- Cash Forecast: are timing assumptions too optimistic?
- Board Deck: is the narrative stronger than the numbers support?

### Phase 1: Spec Lock

Purpose:

- agree on the actual decision or story specification
- capture flip criteria
- move to `PROVISIONAL_LOCK` only when the session is defensible

Examples:

- Variance Copilot: lock the top 3 drivers and recommendation set
- Cash Forecast: lock methodology, scenario thresholds, and alert rules
- Board Generator: lock the storyline, KPI set, and risks before slide generation

### Phase 2: Validation

Purpose:

- validate implementation or final artifact quality
- require third-party confirmation before `LOCKED`

Examples:

- Board Generator: third-party review of narrative and numbers before issue
- Investment Tool: challenge the scoring and recommendation before committee use
- AP Optimizer: validate that payout ranking respects policy and constraints

## Per-Project MVP Notes

### 1. Monthly CFO Variance Copilot

Ship first because it is the cleanest wedge.

MVP:

- upload actuals and budget
- auto-rank the top 3 variance drivers
- generate CFO and CEO summaries
- attach CHP packet and move commentary to `LOCKED` only after partner challenge

### 2. 13-Week Cash Forecast Engine

MVP:

- upload source files
- normalize weekly inflows and outflows
- show red weeks and threshold warnings
- add CHP session for timing risk and action recommendations

### 3. Board Reporting Generator

MVP:

- ingest KPI and financial files
- generate chart-ready outputs and narrative placeholders
- merge leadership commentary
- require CHP hardening before export to `.pptx`

### 4. AP Cash & Payables Optimizer

MVP:

- rank invoices by overdue risk, cash impact, and strategic importance
- let user set weekly cash limit and vendor preference rules
- generate recommended pay list plus CHP review

### 5. 24-Month SaaS Operating Model

MVP:

- expose core drivers
- calculate MRR, burn, cash runway, and hiring trajectory
- run CHP on the model assumptions before leadership review

### 6. CFO Decision Impact Simulator

MVP:

- sliders for pricing, churn, hiring, AR/AP, and shocks
- KPI cards plus cash and EBITDA chart
- CHP summary for the current scenario choice

### 7. SaaS KPI Dashboard

MVP:

- load two CSVs
- calculate missing derived metrics
- present KPI cards and charts
- optionally attach CHP narrative lock for monthly reporting

### 8. Investment Committee Scoring Tool

MVP:

- score proposals against the rubric
- capture evidence quality and gaps
- run CHP challenge before the final recommendation is shared

### 9. SEC / Earnings / Company Research Workbench

MVP:

- ingest public docs
- produce a research dossier with source links
- run CHP on thesis, risks, and valuation claims

### 10. Multi-Agent CFO Operating System

MVP:

- reuse the current orchestrator and CHP package
- add durable decision registry across finance workflows
- make finance, strategy, and compliance collaborate around shared locks

## Implementation Guidance

Use a shared architecture across the roadmap:

- `cme/chp/` for hardening logic, gates, registry, packets, and validations
- `cme/finance/` for domain adapters
- `Excel` skill for workbook-backed workflows
- `PowerPoint` skill for board deck generation

This keeps CHP as the durable substrate instead of a one-off feature inside each app.

## Immediate Recommendation

Implement next in this order:

1. Monthly CFO Variance Copilot
2. 13-Week Cash Forecast Engine
3. Board Reporting Generator

These three maximize speed, usefulness, and visible differentiation.
