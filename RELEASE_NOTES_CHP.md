# Release Notes: Consensus Hardening Protocol (CHP)

## Summary

This release introduces the first **Consensus Hardening Protocol (CHP)** workflow to the repository.

CHP adds a decision-hardening layer for high-stakes finance workflows. Instead of relying on a single model output, it structures a decision as a session with explicit assumptions, vulnerabilities, partner feedback, and third-party validation before final lock.

The first implementation focuses on **capital allocation** as the wedge use case.

## What is included

### New CHP package

New modules under `src/cme/chp/` provide the core CHP scaffold:

- canonical data models for decision cases, dossiers, rounds, and validations
- payload helpers for packet creation and integrity checks
- model parity assessment
- R0 and phase gate logic
- foundation-stage helpers
- registry and persistence support
- orchestration helpers for CHP session startup and follow-on actions

### Capital allocation adapter

New finance-domain code under `src/cme/finance/` builds a normalized capital allocation case for CHP sessions, including:

- decision dossier
- foundation disclosure
- foundation attack
- initial decision scaffolding

### New CLI commands

CHP is now exposed via:

- `cme chp-start`
- `cme chp-receive`
- `cme chp-validate`

These commands support a basic end-to-end flow:

1. initialize a decision session
2. ingest a partner packet
3. apply third-party validation
4. move an item to `LOCKED`

### Demo package

This release also adds a GitHub-friendly CHP demo package:

- `CHP_DEMO_VIDEO.md`
- `examples/chp_demo_video.sh`
- `examples/chp_demo_partner_packet.txt`
- `docs/media/README.md`

The package is designed to make recording and publishing a deterministic CHP demo straightforward.

## Why this matters

The existing repo already demonstrates shared context, visible reasoning, and executable workflows.

CHP extends that story into **decision governance**:

- assumptions are surfaced instead of hidden
- adversarial challenge happens before lock
- lock states become explicit
- partner packets and validation logs become durable artifacts

That is especially relevant for finance use cases where false consensus is expensive.

## Current scope

This is an early scaffold, not a finished product surface.

Current scope includes:

- capital allocation session initialization
- basic partner packet ingestion
- third-party validation flow
- JSON-backed registry persistence
- test coverage for the new CHP primitives and flow skeleton

## What is next

Recommended next steps:

1. add richer packet parsing and round-state transitions
2. add `chp-show` or `chp-export` for session inspection
3. expand CHP into variance review and cash risk workflows
4. add documentation and examples for GitHub-first usage
5. wire the final demo video asset into the README once recorded

## Validation

The CHP additions were verified with the repo test slice covering:

- existing mesh tests
- CHP primitive tests
- CHP capital allocation flow tests
- CHP registry persistence flow tests

Local result:

- `14 passed`
