"""
CoinScopeAI Billing Server — Entry Point

Runs the Stripe webhook handler on port 8002 (separate from engine on 8001).

Usage:
    # Direct (dev):
    python billing_server.py

    # Via uvicorn (recommended for prod):
    uvicorn billing.webhook_handler:app --host 0.0.0.0 --port 8002

    # Stripe CLI forward (test mode):
    stripe listen --forward-to localhost:8002/billing/webhook

Environment variables required:
    STRIPE_SECRET_KEY       — sk_test_... or sk_live_...
    STRIPE_WEBHOOK_SECRET   — whsec_... (from Stripe Dashboard or 'stripe listen' output)
    STRIPE_PRICE_*          — One per tier/interval combination (see .env.template)
    TELEGRAM_BOT_TOKEN      — For billing notifications
    TELEGRAM_CHAT_ID        — Target chat (defaults to Scoopy's chat ID)
    BILLING_DB_PATH         — SQLite path (default: billing_subscriptions.db)
"""

import os
import sys
import logging
from pathlib import Path

# ── Load .env if present ──────────────────────────────────────────────────────
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print(f"[billing_server] Loaded .env from {env_file}")
    except ImportError:
        print("[billing_server] python-dotenv not installed — skipping .env load")

# ── Logging ───────────────────────────────────────────────────────────────────
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("billing_server")

# ── Startup validation ────────────────────────────────────────────────────────
def _validate_config():
    warnings = []
    if not os.getenv("STRIPE_SECRET_KEY"):
        warnings.append("STRIPE_SECRET_KEY not set")
    if not os.getenv("STRIPE_WEBHOOK_SECRET"):
        warnings.append("STRIPE_WEBHOOK_SECRET not set — signature verification DISABLED")
    if not os.getenv("STRIPE_PRICE_PRO_MONTHLY"):
        warnings.append("STRIPE_PRICE_* not configured — tier resolution will return 'unknown'")
    for w in warnings:
        logger.warning(f"[Config] ⚠️  {w}")
    return len(warnings)

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    n_warnings = _validate_config()

    host = os.getenv("BILLING_HOST", "0.0.0.0")
    port = int(os.getenv("BILLING_PORT", "8002"))

    logger.info(f"[billing_server] Starting CoinScopeAI Billing Webhook on {host}:{port}")
    logger.info(f"[billing_server] Webhook endpoint: POST http://{host}:{port}/billing/webhook")
    logger.info(f"[billing_server] Health check:     GET  http://localhost:{port}/billing/health")
    if n_warnings:
        logger.warning(f"[billing_server] {n_warnings} config warning(s) — check .env")

    uvicorn.run(
        "billing.webhook_handler:app",
        host=host,
        port=port,
        reload=False,
        log_level=log_level.lower(),
    )
