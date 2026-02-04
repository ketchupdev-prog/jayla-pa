#!/usr/bin/env bash
# Set Railway service variables from .env (run from jayla-pa with railway linked).
# Skips comments and empty lines. Values passed via stdin to avoid command-line exposure.

set -e
cd "$(dirname "$0")/.."
[ -f .env ] || { echo ".env not found"; exit 1; }

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%%#*}"
  line="$(echo "$line" | xargs)"
  [[ -z "$line" ]] && continue
  if [[ "$line" == *=* ]]; then
    key="${line%%=*}"
    key="$(echo "$key" | xargs)"
    val="${line#*=}"
    val="${val#\"}"
    val="${val%\"}"
    [[ -z "$key" ]] && continue
    [[ -z "$val" ]] && continue
    # Skip CLI-only tokens (not needed by the running app)
    [[ "$key" == "RAILWAY_TOKEN" ]] && continue
    printf '%s' "$val" | railway variable set "$key" --stdin --skip-deploys
  fi
done < .env

echo "Variables set. Run: railway up"
