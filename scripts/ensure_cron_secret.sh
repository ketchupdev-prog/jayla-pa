#!/usr/bin/env bash
# Generate CRON_SECRET and add or replace in .env using sed. Run from jayla-pa.
# Then run ./scripts/set_railway_vars.sh to sync to Railway.

set -e
cd "$(dirname "$0")/.."
CRON_VAL=$(openssl rand -hex 24 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(24))")
if [ -f .env ]; then
  if grep -q '^CRON_SECRET=' .env 2>/dev/null; then
    if sed --version 2>/dev/null | grep -q GNU; then
      sed -i "s|^CRON_SECRET=.*|CRON_SECRET=$CRON_VAL|" .env
    else
      sed -i.bak "s|^CRON_SECRET=.*|CRON_SECRET=$CRON_VAL|" .env && rm -f .env.bak
    fi
  else
    echo "CRON_SECRET=$CRON_VAL" >> .env
  fi
  echo "CRON_SECRET set in .env (value not printed). Run: ./scripts/set_railway_vars.sh"
else
  echo ".env not found; create from .env.example first"
  exit 1
fi
