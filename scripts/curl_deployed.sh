#!/usr/bin/env bash
# Run curl against the deployed Jayla PA. Set BASE_URL to your Railway domain.
# Railway: Settings → Networking → Public Networking → copy the *.up.railway.app URL.
# Custom domain: use https://jayla.ketchup.cc
BASE_URL="${BASE_URL:-https://jayla.ketchup.cc}"

echo "=== BASE_URL: $BASE_URL ==="
echo ""

echo "GET / (root)"
curl -s "$BASE_URL/" | jq . 2>/dev/null || curl -s "$BASE_URL/"
echo -e "\n"

echo "GET /health"
curl -s "$BASE_URL/health" | jq . 2>/dev/null || curl -s "$BASE_URL/health"
echo -e "\n"

echo "POST /webhook (empty body, expect 200 + ok:true)"
curl -s -X POST "$BASE_URL/webhook" -H "Content-Type: application/json" -d '{}' | jq . 2>/dev/null || curl -s -X POST "$BASE_URL/webhook" -H "Content-Type: application/json" -d '{}'
echo ""
