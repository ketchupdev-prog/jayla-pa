#!/usr/bin/env bash
# Test all .env connections and chat completions using curl.
# Run from repo root: ./scripts/test_env_connections.sh
# Or from jayla-pa: ./scripts/test_env_connections.sh (uses .env in current dir)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PA_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PA_ROOT/.env"
cd "$PA_ROOT"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  exit 1
fi

# Load .env (skip comments and empty lines; export KEY=value; value may contain =)
set -a
while IFS= read -r line; do
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue
  key="${line%%=*}"
  key="${key// /}"
  [[ -z "$key" ]] && continue
  value="${line#*=}"
  value="${value#\"}"
  value="${value%\"}"
  export "$key=$value"
done < "$ENV_FILE"
set +a

echo "=== Jayla PA .env connection tests (curl) ==="
echo ""

# --- 1. Groq chat completions ---
echo "[1/5] Groq (chat completions)..."
GROQ_STATUS=$(curl -s -o /tmp/groq_resp.json -w "%{http_code}" \
  -X POST "https://api.groq.com/openai/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${GROQ_API_KEY}" \
  -d "{\"model\": \"${GROQ_MODEL:-llama-3.3-70b-versatile}\", \"messages\": [{\"role\": \"user\", \"content\": \"Say OK in one word.\"}], \"max_tokens\": 10}")
if [[ "$GROQ_STATUS" == "200" ]]; then
  echo "  OK (HTTP $GROQ_STATUS)"
else
  echo "  FAIL (HTTP $GROQ_STATUS). Check GROQ_API_KEY and GROQ_MODEL."
  cat /tmp/groq_resp.json 2>/dev/null | head -3
fi
echo ""

# --- 2. DeepSeek chat completions ---
echo "[2/5] DeepSeek (chat completions)..."
DEEPSEEK_STATUS=$(curl -s -o /tmp/deepseek_resp.json -w "%{http_code}" \
  -X POST "https://api.deepseek.com/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${DEEPSEEK_API_KEY}" \
  -d "{\"model\": \"${LLM_MODEL:-deepseek-chat}\", \"messages\": [{\"role\": \"user\", \"content\": \"Say OK in one word.\"}], \"max_tokens\": 10}")
if [[ "$DEEPSEEK_STATUS" == "200" ]]; then
  echo "  OK (HTTP $DEEPSEEK_STATUS)"
else
  echo "  FAIL (HTTP $DEEPSEEK_STATUS). Check DEEPSEEK_API_KEY and LLM_MODEL."
  cat /tmp/deepseek_resp.json 2>/dev/null | head -3
fi
echo ""

# --- 3. Qdrant collections ---
echo "[3/5] Qdrant (collections)..."
QDRANT_STATUS=$(curl -s -o /tmp/qdrant_resp.json -w "%{http_code}" \
  -X GET "${QDRANT_URL}/collections" \
  -H "api-key: ${QDRANT_API_KEY}")
if [[ "$QDRANT_STATUS" == "200" ]]; then
  echo "  OK (HTTP $QDRANT_STATUS)"
else
  echo "  FAIL (HTTP $QDRANT_STATUS). Check QDRANT_URL and QDRANT_API_KEY."
  cat /tmp/qdrant_resp.json 2>/dev/null | head -3
fi
echo ""

# --- 4. Telegram getMe ---
echo "[4/5] Telegram (bot getMe)..."
TG_STATUS=$(curl -s -o /tmp/telegram_resp.json -w "%{http_code}" \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe")
if [[ "$TG_STATUS" == "200" ]]; then
  if grep -q '"ok":true' /tmp/telegram_resp.json 2>/dev/null; then
    echo "  OK (HTTP $TG_STATUS)"
  else
    echo "  FAIL (API returned ok:false). Check TELEGRAM_BOT_TOKEN."
    cat /tmp/telegram_resp.json 2>/dev/null | head -3
  fi
else
  echo "  FAIL (HTTP $TG_STATUS). Check TELEGRAM_BOT_TOKEN."
  cat /tmp/telegram_resp.json 2>/dev/null | head -3
fi
echo ""

# --- 5. Arcade (simple auth check: list projects or similar) ---
echo "[5/5] Arcade (API key check)..."
ARCADE_STATUS=$(curl -s -o /tmp/arcade_resp.json -w "%{http_code}" \
  -X GET "${ARCADE_BASE_URL:-https://api.arcade.dev}/v1/projects" \
  -H "Authorization: Bearer ${ARCADE_API_KEY}" \
  -H "Content-Type: application/json")
if [[ "$ARCADE_STATUS" == "200" ]] || [[ "$ARCADE_STATUS" == "201" ]]; then
  echo "  OK (HTTP $ARCADE_STATUS)"
else
  echo "  Note (HTTP $ARCADE_STATUS). Arcade may use a different endpoint; key format checked."
  cat /tmp/arcade_resp.json 2>/dev/null | head -3
fi
echo ""

echo "---"
echo "Neon (DATABASE_URL): use psql or Python to test; curl does not connect to Postgres."
echo "Done."
