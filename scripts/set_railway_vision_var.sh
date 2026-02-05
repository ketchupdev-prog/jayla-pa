#!/usr/bin/env bash
# Set GROQ_VISION_MODEL on Railway (run from jayla-pa with: railway link).
# Use this if GROQ_VISION_MODEL is missing in Railway Variables.
# Full sync: use set_railway_vars.sh instead.

set -e
cd "$(dirname "$0")/.."
DEFAULT="llama-3.2-90b-vision-preview"
# Prefer value from .env if present
if [ -f .env ] && grep -q '^GROQ_VISION_MODEL=' .env 2>/dev/null; then
  VALUE=$(grep '^GROQ_VISION_MODEL=' .env | cut -d= -f2- | sed 's/^"//;s/"$//;s/^'"'"'//;s/'"'"'$//')
  VALUE="${VALUE:-$DEFAULT}"
else
  VALUE="${DEFAULT}"
fi
echo "Setting GROQ_VISION_MODEL on Railway..."
printf '%s' "$VALUE" | railway variable set GROQ_VISION_MODEL --stdin
echo "Done. Redeploy or push a commit to apply."
