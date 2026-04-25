#!/usr/bin/env bash
set -euo pipefail

REGISTRY_FILE="${1:-.chp_demo_registry.json}"
PARTNER_PACKET="examples/chp_demo_partner_packet.txt"

echo
echo "== CHP DEMO: start session =="
PYTHONPATH=src python3 -m cme.cli chp-start \
  --registry "$REGISTRY_FILE" \
  --title "Fund enterprise workflow" \
  --company "Acme" \
  --problem "Should we fund a new enterprise workflow team this quarter?" \
  --amount 2500000 \
  --payback-months 14 \
  --min-runway 12 \
  --current-runway 18 \
  --priority "Expand enterprise ARR" \
  --priority "Preserve capital discipline" \
  --risk "Adoption lag" \
  --risk "Implementation complexity" \
  --upside "Higher ACV" \
  --upside "Lower churn in strategic accounts"

echo
echo "== CHP DEMO: receive partner packet =="
PYTHONPATH=src python3 -m cme.cli chp-receive \
  --registry "$REGISTRY_FILE" \
  --decision-id "cap-fund-enterprise-workflow" \
  --packet-file "$PARTNER_PACKET" \
  --phase 1 \
  --round 1 \
  --status PROVISIONAL_LOCK \
  --payload-echo "[RX] [CHP001] CONFIRMED"

echo
echo "== CHP DEMO: third-party validation =="
PYTHONPATH=src python3 -m cme.cli chp-validate \
  --registry "$REGISTRY_FILE" \
  --decision-id "cap-fund-enterprise-workflow" \
  --validator "fresh_instance" \
  --item "Investment spec v1" \
  --challenge "Stress test payback under slower adoption" \
  --result CONFIRM \
  --rationale "The case remains coherent with milestone-gated capital release."

echo
echo "== CHP DEMO COMPLETE =="
echo "Registry written to: $REGISTRY_FILE"
