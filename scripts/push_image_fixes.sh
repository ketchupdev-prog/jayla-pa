#!/bin/bash
# Push jayla-pa image/vision fixes to GitHub.
# Run from the repo that has .git (either ai-agent-mastery-main if it's a clone, or your repo root).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PA_ROOT="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$PA_ROOT/../.." 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null)" || true

if [ -n "$REPO_ROOT" ] && [ -d "$REPO_ROOT/.git" ]; then
  cd "$REPO_ROOT"
  # Paths relative to repo root (e.g. jayla-pa/... if repo is ai-agent-mastery-main)
  if [ -f "jayla-pa/prompts.py" ]; then
    git add jayla-pa/prompts.py jayla-pa/tools.py jayla-pa/nodes.py jayla-pa/telegram_bot/webhook.py jayla-pa/scripts/test_tool_calls.py
  else
    git add "$PA_ROOT/prompts.py" "$PA_ROOT/tools.py" "$PA_ROOT/nodes.py" "$PA_ROOT/telegram_bot/webhook.py" "$PA_ROOT/scripts/test_tool_calls.py" 2>/dev/null || true
  fi
  git status -s
  git commit -m "jayla-pa: image generation and photo description always work

- Prompts: CRITICAL block at top for generate_image and [Image: ...]; never say no image gen
- Tools: load generate_image even when Arcade fails (try/except get_manager)
- Nodes: handle missing Arcade manager so generate_image runs without auth
- Webhook: sys.path for vision; reply when vision fails
- test_tool_calls: test_image_gen_tool, generate_image in prompts"
  git push
  echo "Pushed."
else
  echo "Run from repo root (where .git is). Example:"
  echo "  cd /path/to/ai-agent-mastery-main"
  echo "  git add jayla-pa/prompts.py jayla-pa/telegram_bot/webhook.py jayla-pa/scripts/test_tool_calls.py"
  echo "  git commit -m 'jayla-pa: fix image handling and image generation'"
  echo "  git push"
fi
