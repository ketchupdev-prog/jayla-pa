#!/usr/bin/env bash
# Set Railway service variables from .env (run from jayla-pa with railway linked).
# Skips comments and empty lines. Values passed via stdin to avoid command-line exposure.
# IMPORTANT: For web search in Telegram, add BRAVE_API_KEY to .env (get key at https://brave.com/search/api).

set -e
cd "$(dirname "$0")/.."
[ -f .env ] || { echo ".env not found"; exit 1; }

# Remind if BRAVE_API_KEY is missing (web search won't work on Railway without it)
if ! grep -q '^BRAVE_API_KEY=.\+' .env 2>/dev/null; then
  echo "Note: BRAVE_API_KEY is empty or missing in .env. Web search in Telegram will not work until you add it to .env and re-run this script (or set it in Railway Variables)."
fi

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

echo "Variables set. Run: railway up (or push a commit to trigger deploy)."
echo "If web search in Telegram should work, ensure BRAVE_API_KEY was set (check Railway → Variables)."
