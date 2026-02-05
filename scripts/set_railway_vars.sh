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
# Remind if GROQ_API_KEY / GROQ_VISION_MODEL (vision for photos)
if ! grep -q '^GROQ_API_KEY=.\+' .env 2>/dev/null; then
  echo "Note: GROQ_API_KEY is empty or missing. Vision (describe photos) and chat/STT will not work until you add it and re-run (or set in Railway Variables)."
fi
if ! grep -q '^GROQ_VISION_MODEL=.\+' .env 2>/dev/null; then
  echo "Note: GROQ_VISION_MODEL not in .env (optional). Default: llama-3.2-90b-vision-preview. Add it to override on Railway."
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
echo "If vision (describe photos) should work, ensure GROQ_API_KEY and optionally GROQ_VISION_MODEL are set (check Railway → Variables)."
