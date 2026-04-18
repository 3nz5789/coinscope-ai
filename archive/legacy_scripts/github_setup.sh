#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  CoinScopeAI — GitHub Repository Setup Script
#
#  Run this ONCE from inside your CoinScopeAI project folder.
#  Before running: create the empty GitHub repo (instructions in README).
#
#  Usage:
#    chmod +x github_setup.sh
#    ./github_setup.sh YOUR_GITHUB_USERNAME
# ─────────────────────────────────────────────────────────────────────────────

set -e

GITHUB_USERNAME="${1:-YOUR_USERNAME}"
REPO_NAME="coinscope-ai"
REMOTE_URL="https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"

echo ""
echo "┌─────────────────────────────────────────────┐"
echo "│   CoinScopeAI — GitHub Setup                │"
echo "└─────────────────────────────────────────────┘"
echo ""

# ── Safety check: confirm .env is gitignored ────────────────────────────────
if [ -f ".env" ]; then
  if git check-ignore -q .env 2>/dev/null || grep -q "^\.env$" .gitignore; then
    echo "✅ .env is gitignored — safe to proceed"
  else
    echo "❌ ERROR: .env is NOT in .gitignore. Aborting to protect your secrets."
    exit 1
  fi
fi

# ── Remove duplicate engine folders ─────────────────────────────────────────
echo "🧹 Cleaning up duplicate folders..."
rm -rf "coinscope_trading_engine 2" "coinscope_trading_engine 3" "coinscope_trading_engine 4" 2>/dev/null || true
rm -f coinscope_trading_engine.tar.gz market_scanner_skill.zip 2>/dev/null || true
echo "✅ Cleaned"

# ── Initialise git ───────────────────────────────────────────────────────────
echo ""
echo "⚙️  Initialising git repository..."
git init
git branch -M main

# ── Stage all files ──────────────────────────────────────────────────────────
echo "📦 Staging files..."
git add .

# ── Verify no secrets are staged ────────────────────────────────────────────
echo ""
echo "🔍 Scanning staged files for secrets..."
if git diff --cached --name-only | xargs grep -l "api_key\s*=\s*['\"][A-Za-z0-9]\{20,\}" 2>/dev/null | grep -v ".gitignore\|.env.example\|#"; then
  echo "❌ WARNING: Possible hardcoded key found in staged files!"
  echo "   Review the files above before pushing."
  exit 1
fi
echo "✅ No hardcoded secrets detected"

# ── First commit ─────────────────────────────────────────────────────────────
echo ""
echo "💾 Creating initial commit..."
git commit -m "feat: initial CoinScopeAI project setup

- FastAPI trading engine with FixedScorer (0-12 signal scoring)
- HMM regime detection (Bull/Bear/Chop)
- Kelly Criterion position sizing
- Risk Gate circuit breakers
- Notion trade journal integration
- Binance Futures testnet clients (REST + WebSocket)
- Telegram alert system
- Manus agent skill definitions
- GitHub Actions CI with secret scanning"

# ── Connect to GitHub ────────────────────────────────────────────────────────
echo ""
echo "🔗 Connecting to GitHub..."
git remote add origin "${REMOTE_URL}"
echo "✅ Remote set to: ${REMOTE_URL}"

# ── Push ─────────────────────────────────────────────────────────────────────
echo ""
echo "🚀 Pushing to GitHub..."
git push -u origin main

echo ""
echo "┌─────────────────────────────────────────────┐"
echo "│   ✅ Done! Repository is live on GitHub.    │"
echo "│                                             │"
echo "│   Next steps:                               │"
echo "│   1. Add repo secrets (Settings → Secrets) │"
echo "│   2. Create 'develop' branch                │"
echo "│   3. Enable branch protection on main      │"
echo "└─────────────────────────────────────────────┘"
echo ""
echo "   🔗 https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
echo ""
