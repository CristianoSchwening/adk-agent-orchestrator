#!/usr/bin/env bash
# Sync Replit → GitHub (Replit é a fonte da verdade).
# Execute no Shell do Replit: bash scripts/git_autopush.sh

set -euo pipefail

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "ERROR: GITHUB_TOKEN não encontrado nos Secrets do Replit."
  exit 1
fi

REPO="CristianoSchwening/adk-agent-orchestrator"
AUTH_REMOTE="https://${GITHUB_TOKEN}@github.com/${REPO}"

# ── Abortar rebase em andamento, se houver ────────────────────────────────────
if [ -d "$(git rev-parse --git-dir)/rebase-merge" ] || \
   [ -d "$(git rev-parse --git-dir)/rebase-apply" ]; then
  echo "⚠ Rebase em andamento detectado — abortando..."
  git rebase --abort
  echo "✓ Rebase abortado. Continuando com o push..."
  echo ""
fi

# ── Mostrar commits pendentes ─────────────────────────────────────────────────
echo "→ Commits locais que serão enviados ao GitHub:"
git log --oneline HEAD 2>/dev/null | head -10
echo ""

# ── Force push: Replit é a fonte da verdade ───────────────────────────────────
echo "→ Enviando para GitHub (--force)..."
git push --force "$AUTH_REMOTE" main

echo ""
echo "✅ Push concluído! GitHub agora está sincronizado com o Replit."
echo "   Veja em: https://github.com/${REPO}/commits/main"
echo ""
echo "⚠ Se você tiver uma cópia local no Windows, sincronize assim:"
echo "   git fetch origin"
echo "   git reset --hard origin/main"
