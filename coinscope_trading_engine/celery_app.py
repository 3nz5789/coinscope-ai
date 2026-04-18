"""
celery_app.py — Celery Application Factory
===========================================
Creates and configures the Celery application instance used by all tasks.

Broker  : Redis (redis://localhost:6379/0)
Backend : Redis (redis://localhost:6379/1)

Start workers
-------------
    # Default (all queues):
    celery -A celery_app worker --loglevel=info

    # Heavy ML tasks only (dedicated GPU/CPU worker):
    celery -A celery_app worker -Q ml_tasks --loglevel=info --concurrency=2

    # Alerts only (lightweight, high concurrency):
    celery -A celery_app worker -Q alerts --loglevel=info --concurrency=8

    # Scheduled beats (cron tasks):
    celery -A celery_app beat --loglevel=info

Monitor
-------
    celery -A celery_app flower --port=5555
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange

# ---------------------------------------------------------------------------
# Redis URLs
# ---------------------------------------------------------------------------

REDIS_URL     = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
REDIS_BACKEND = os.environ.get("REDIS_BACKEND_URL", "redis://localhost:6379/1")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

celery_app = Celery(
    "coinscopeai",
    broker  = REDIS_URL,
    backend = REDIS_BACKEND,
    include = ["tasks"],   # auto-import tasks.py on worker start
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

celery_app.conf.update(
    # Serialisation
    task_serializer         = "json",
    result_serializer       = "json",
    accept_content          = ["json"],

    # Timezone
    timezone                = "UTC",
    enable_utc              = True,

    # Reliability
    task_acks_late              = True,    # ack only after task completes
    task_reject_on_worker_lost  = False,   # do NOT re-queue on worker death
                                            # prevents duplicate Telegram messages
                                            # (dispatch_telegram_alert uses acks_late=False
                                            #  so the task is already ACKed before execution)
    task_track_started          = True,    # lets beat/flower show "STARTED"

    # Results
    result_expires          = 3_600,       # expire results after 1 h

    # Rate limits
    task_default_rate_limit = "60/m",

    # Routing — three named queues
    task_default_queue      = "default",
    task_queues             = (
        Queue("default",   Exchange("default"),   routing_key="default"),
        Queue("ml_tasks",  Exchange("ml_tasks"),  routing_key="ml"),
        Queue("alerts",    Exchange("alerts"),    routing_key="alerts"),
        Queue("scanning",  Exchange("scanning"),  routing_key="scan"),
    ),
    task_routes = {
        "tasks.run_regime_detection":    {"queue": "ml_tasks"},
        "tasks.run_price_prediction":    {"queue": "ml_tasks"},
        "tasks.run_anomaly_detection":   {"queue": "ml_tasks"},
        "tasks.dispatch_telegram_alert": {"queue": "alerts"},
        "tasks.dispatch_webhook_alert":  {"queue": "alerts"},
        "tasks.run_scan_cycle":          {"queue": "scanning"},
        "tasks.send_daily_summary":      {"queue": "alerts"},
    },

    # Beat schedule (periodic tasks)
    beat_schedule = {
        # Full scan every 5 minutes
        "scan-all-pairs": {
            "task":     "tasks.run_scan_cycle",
            "schedule": 300,   # seconds
            "args":     (),
        },
        # Daily summary at 00:00 UTC
        "daily-summary": {
            "task":     "tasks.send_daily_summary",
            "schedule": crontab(hour=0, minute=0),
            "args":     (),
        },
        # Regime re-detection every 10 minutes
        "regime-check": {
            "task":     "tasks.run_regime_detection",
            "schedule": 600,
            "args":     (),
        },
    },

    # Worker
    worker_prefetch_multiplier  = 1,    # one task at a time per process
    worker_max_tasks_per_child  = 200,  # recycle workers to prevent memory leaks
)
