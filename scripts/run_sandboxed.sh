#!/usr/bin/env bash
# Launch Claw inside an OpenShell sandbox.
# Prerequisites: openshell installed (uv tool install -U openshell)
#
# Usage:
#   bash scripts/run_sandboxed.sh                  # start all agents
#   bash scripts/run_sandboxed.sh --report         # one-shot analysis
#   bash scripts/run_sandboxed.sh --report --date 2026-05-15

set -euo pipefail

if ! command -v openshell &>/dev/null; then
  echo "openshell not found. Install with: uv tool install -U openshell"
  exit 1
fi

if [[ -z "${NVIDIA_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Warning: neither NVIDIA_API_KEY nor OPENAI_API_KEY is set."
fi

POLICY_FILE="$(dirname "$0")/../openshell_policy.yaml"

exec openshell sandbox create \
  --policy "$POLICY_FILE" \
  ${NVIDIA_API_KEY:+--provider nvidia-api-key="$NVIDIA_API_KEY"} \
  ${OPENAI_API_KEY:+--provider openai-api-key="$OPENAI_API_KEY"} \
  ${SLACK_BOT_TOKEN:+--provider slack-bot-token="$SLACK_BOT_TOKEN"} \
  -- python main.py "$@"
