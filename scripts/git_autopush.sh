#!/usr/bin/env bash
# Sync Replit commits → GitHub.
# Execute no Shell do Replit: bash scripts/git_autopush.sh

set -euo pipefail

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "ERROR: GITHUB_TOKEN não encontrado nos Secrets do Replit."
  exit 1
fi

REPO="CristianoSchwening/adk-agent-orchestrator"
AUTH_REMOTE="https://${GITHUB_TOKEN}@github.com/${REPO}"

echo "→ Commits locais pendentes:"
git log --oneline HEAD 2>/dev/null | head -8
echo ""

echo "→ Buscando commits do GitHub que ainda não estão no Replit..."
git fetch "$AUTH_REMOTE" main:refs/remotes/github/main 2>&1 | grep -v "^$" || true

echo ""
echo "→ Integrando commits do GitHub (rebase)..."
git rebase refs/remotes/github/main || {
  echo ""
  echo "⚠ Conflitos de merge detectados!"
  echo "  Resolva os conflitos nos arquivos marcados, depois execute:"
  echo "    git add <arquivo>"
  echo "    git rebase --continue"
  echo "  E então rode este script novamente."
  exit 1
}

echo ""
echo "→ Enviando para GitHub..."
git push "$AUTH_REMOTE" main

echo ""
echo "✅ Push concluído!"
echo "   Veja em: https://github.com/${REPO}/commits/main"
