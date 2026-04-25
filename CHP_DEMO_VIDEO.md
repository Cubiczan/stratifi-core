# CHP Demo Video Package

This repo now includes a short, GitHub-friendly CHP demo flow you can record and publish alongside the codebase.

## What this demo shows

The demo is designed to make one point clearly:

`CHP is not just another finance analysis prompt.`

It shows a capital allocation decision moving through three visible stages:

1. Session initialization with a decision dossier
2. Partner packet ingestion with a provisional lock
3. Third-party validation that promotes the item to `LOCKED`

That gives you a concrete GitHub story:

- deterministic local demo
- visible state progression
- auditable packet exchange
- explicit lock logic

## Recording format

Recommended output:

- Length: 60-90 seconds
- Format: terminal-only screen recording
- Resolution: 1440p or 1080p
- Destination: `docs/media/chp-demo.mp4` after recording

This environment can prepare the recording assets, but it does not directly render an `.mp4` for you. The files below are meant to make recording fast and repeatable.

## Files included

- `examples/chp_demo_video.sh`
- `examples/chp_demo_partner_packet.txt`

## Recording setup

From the repo root:

```bash
cd cognitive-mesh-orchestrator
chmod +x examples/chp_demo_video.sh
```

Use a clean terminal theme and large font. Keep one terminal pane only.

## Demo run

```bash
./examples/chp_demo_video.sh
```

## Suggested narration

### 0:00 - 0:15

> This is Consensus Hardening Protocol, or CHP. Instead of taking a single-model answer at face value, it turns a finance decision into a hardened, auditable session with visible lock states.

### 0:15 - 0:35

> First, we start a capital allocation session. CHP builds the dossier, checks context, assesses model parity, runs the initial gate, and produces the first decision packet.

### 0:35 - 0:55

> Next, we ingest a partner response. The important part is not just agreement, it is tracked agreement with payload integrity and an explicit state change to provisional lock.

### 0:55 - 1:15

> Finally, we apply third-party validation. Only then does the item move from provisional lock to locked. That is the core discipline: consensus is not enough until it is hardened.

### 1:15 - 1:25

> This is the foundation for capital allocation, variance review, and cash risk workflows where false consensus is expensive.

## Shot list

1. Show `PYTHONPATH=src python3 -m cme.cli --help`
2. Run `./examples/chp_demo_video.sh`
3. Pause briefly after each block:
   - `chp-start`
   - `chp-receive`
   - `chp-validate`
4. End on the final `LOCKED` output

## Optional GitHub placement

After you record the video, place it at:

```text
docs/media/chp-demo.mp4
```

Then you can reference it from the README using a standard link, for example:

```md
[Watch the CHP demo video](docs/media/chp-demo.mp4)
```

Or upload it to GitHub Releases and link to that asset.

## If you want a slightly more polished version

Record two takes:

- one silent terminal-only take for GitHub
- one narrated take for LinkedIn or X

Use the exact same shell script for both so the behavior stays consistent.
