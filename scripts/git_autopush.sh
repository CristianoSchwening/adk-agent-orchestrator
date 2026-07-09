#!/usr/bin/env bash
# Push Replit commits to GitHub.
# Execute no Shell do Replit: bash scripts/git_autopush.sh

set -euo pipefail

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "ERROR: GITHUB_TOKEN não encontrado."
  echo "Verifique se o secret está configurado em Secrets (cadeado) no Replit."
  exit 1
fi

REPO="CristianoSchwening/adk-agent-orchestrator"
AUTH_REMOTE="https://${GITHUB_TOKEN}@github.com/${REPO}"
PUBLIC_REMOTE="https://github.com/${REPO}"

echo "→ Commits locais ainda não enviados ao GitHub:"
git log --oneline origin/main..HEAD 2>/dev/null || git log --oneline -5

echo ""
echo "→ Enviando para GitHub..."
git push "$AUTH_REMOTE" main

echo ""
echo "✅ Push concluído! Veja em: $PUBLIC_REMOTE/commits/main"
