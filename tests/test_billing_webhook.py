"""
Billing Webhook Tests
Tests for: signature verification, event routing, idempotency, subscription store.

Run:
    cd /path/to/CoinScopeAI
    python -m pytest tests/test_billing_webhook.py -v
"""

import os
import json
import time
import hmac
import hashlib
import tempfile
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ── Test environment setup ────────────────────────────────────────────────────
TEST_WEBHOOK_SECRET = "whsec_test_secret_1234567890abcdef"
TEST_PRICE_PRO_MONTHLY = "price_pro_monthly_test"
TEST_PRICE_STARTER_MONTHLY = "price_starter_monthly_test"
TEST_PRICE_ELITE_ANNUAL = "price_elite_annual_test"

os.environ["STRIPE_SECRET_KEY"]          = "sk_test_fake"
os.environ["STRIPE_WEBHOOK_SECRET"]      = TEST_WEBHOOK_SECRET
os.environ["STRIPE_PRICE_PRO_MONTHLY"]   = TEST_PRICE_PRO_MONTHLY
os.environ["STRIPE_PRICE_STARTER_MONTHLY"] = TEST_PRICE_STARTER_MONTHLY
os.environ["STRIPE_PRICE_ELITE_ANNUAL"]  = TEST_PRICE_ELITE_ANNUAL
os.environ["TELEGRAM_BOT_TOKEN"]         = ""   # Disable telegram in tests
os.environ["TELEGRAM_CHAT_ID"]           = ""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from billing.models import SubscriptionTier, SubscriptionStatus, BillingInterval
from billing.subscription_store import SubscriptionStore, SubscriptionRecord

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_stripe_sig(payload: bytes, secret: str, timestamp: int = None) -> str:
    """Construct a Stripe webhook signature header (same algorithm Stripe uses)."""
    if timestamp is None:
        timestamp = int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload
    mac = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={mac}"


# Counter for deterministic unique event IDs (avoid same-second collisions)
_event_counter = 0

def _event(event_type: str, data: dict) -> dict:
    """Build a minimal Stripe v1 event envelope (stripe SDK v15 compatible)."""
    global _event_counter
    _event_counter += 1
    return {
        "id": f"evt_test_{_event_counter:04d}_{event_type.replace('.', '_')}",
        "object": "event",          # Required by stripe SDK v15 construct_event
        "api_version": "2023-10-16",
        "type": event_type,
        "data": {"object": data},
    }


def _post_event(client, event_type: str, data: dict, secret: str = TEST_WEBHOOK_SECRET):
    """Post a signed Stripe event to the webhook endpoint."""
    body = json.dumps(_event(event_type, data)).encode()
    sig  = _make_stripe_sig(body, secret)
    return client.post(
        "/billing/webhook",
        content=body,
        headers={"stripe-signature": sig, "content-type": "application/json"},
    )


# ── SubscriptionStore unit tests ──────────────────────────────────────────────

class TestSubscriptionStore:
    """Tests for SQLite subscription persistence."""

    @pytest.fixture(autouse=True)
    def tmp_db(self, tmp_path):
        """Use a temp DB for each test."""
        db_path = str(tmp_path / "test_billing.db")
        self.store = SubscriptionStore(db_path=db_path)

    def _make_record(self, customer_id="cus_test001", sub_id="sub_test001", tier=SubscriptionTier.PRO):
        return SubscriptionRecord(
            customer_id=customer_id,
            email="test@example.com",
            stripe_subscription_id=sub_id,
            tier=tier,
            status=SubscriptionStatus.ACTIVE,
            interval=BillingInterval.MONTHLY,
            cancel_at_period_end=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def test_upsert_and_retrieve_by_customer(self):
        record = self._make_record()
        self.store.upsert_subscription(record)
        fetched = self.store.get_subscription_by_customer("cus_test001")
        assert fetched is not None
        assert fetched.tier == SubscriptionTier.PRO
        assert fetched.email == "test@example.com"

    def test_upsert_updates_existing_record(self):
        record = self._make_record()
        self.store.upsert_subscription(record)

        # Update tier
        record.tier = SubscriptionTier.ELITE
        self.store.upsert_subscription(record)

        fetched = self.store.get_subscription_by_customer("cus_test001")
        assert fetched.tier == SubscriptionTier.ELITE

    def test_retrieve_by_stripe_subscription_id(self):
        record = self._make_record(sub_id="sub_findme")
        self.store.upsert_subscription(record)
        fetched = self.store.get_subscription_by_stripe_id("sub_findme")
        assert fetched is not None

    def test_cancel_subscription(self):
        record = self._make_record()
        self.store.upsert_subscription(record)
        self.store.cancel_subscription("cus_test001")
        fetched = self.store.get_subscription_by_customer("cus_test001")
        assert fetched.status == SubscriptionStatus.CANCELED

    def test_idempotency_mark_and_check(self):
        assert not self.store.is_event_processed("evt_unique_001")
        self.store.mark_event_processed("evt_unique_001", "checkout.session.completed", "cus_x")
        assert self.store.is_event_processed("evt_unique_001")

    def test_idempotency_duplicate_insert_is_safe(self):
        self.store.mark_event_processed("evt_dup", "some.event", "cus_y")
        # Second mark should not raise
        self.store.mark_event_processed("evt_dup", "some.event", "cus_y")
        assert self.store.is_event_processed("evt_dup")

    def test_list_active_subscriptions(self):
        self.store.upsert_subscription(self._make_record("cus_a", "sub_a"))
        canceled = self._make_record("cus_b", "sub_b")
        canceled.status = SubscriptionStatus.CANCELED
        self.store.upsert_subscription(canceled)

        active = self.store.list_active_subscriptions()
        assert len(active) == 1
        assert active[0].customer_id == "cus_a"

    def test_returns_none_for_unknown_customer(self):
        assert self.store.get_subscription_by_customer("cus_nobody") is None


# ── Price resolution tests ────────────────────────────────────────────────────

class TestPriceResolution:
    """Tests for price_id → tier/interval mapping."""

    def test_known_price_resolves_correctly(self):
        from billing.webhook_handler import resolve_price
        tier, interval = resolve_price(TEST_PRICE_PRO_MONTHLY)
        assert tier == SubscriptionTier.PRO
        assert interval == BillingInterval.MONTHLY

    def test_unknown_price_returns_unknown_tier(self):
        from billing.webhook_handler import resolve_price
        tier, interval = resolve_price("price_nonexistent")
        assert tier == SubscriptionTier.UNKNOWN

    def test_elite_annual_resolves(self):
        from billing.webhook_handler import resolve_price
        tier, interval = resolve_price(TEST_PRICE_ELITE_ANNUAL)
        assert tier == SubscriptionTier.ELITE
        assert interval == BillingInterval.ANNUAL


# ── Webhook endpoint integration tests ───────────────────────────────────────

class TestWebhookEndpoint:
    """Integration tests for the FastAPI webhook endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, tmp_path):
        """Patch the store and notifier for each test using temp DB."""
        db_path = str(tmp_path / "webhook_test.db")
        test_store = SubscriptionStore(db_path=db_path)
        mock_notifier = MagicMock()

        import billing.webhook_handler as wh
        # Inject test dependencies via the lazy-singleton globals
        wh._store_instance = test_store
        wh._notifier_instance = mock_notifier

        # Pin the webhook secret for this test class.
        # Another test file (test_billing_portal.py) is collected after this
        # one and overwrites os.environ["STRIPE_WEBHOOK_SECRET"] during pytest
        # collection, before any tests actually run. We restore it here so
        # _webhook_secret() always sees the right value for these tests.
        _orig_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
        os.environ["STRIPE_WEBHOOK_SECRET"] = TEST_WEBHOOK_SECRET

        self.client = TestClient(wh.app, raise_server_exceptions=False)
        self.wh = wh

        yield

        # Cleanup: restore env and reset singletons so next test gets fresh ones
        if _orig_secret is None:
            os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
        else:
            os.environ["STRIPE_WEBHOOK_SECRET"] = _orig_secret
        wh._store_instance = None
        wh._notifier_instance = None

    def test_health_endpoint(self):
        resp = self.client.get("/billing/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["webhook_secret_configured"] is True

    def test_invalid_signature_returns_400(self):
        body = json.dumps({"id": "evt_bad", "type": "test", "data": {"object": {}}}).encode()
        resp = self.client.post(
            "/billing/webhook",
            content=body,
            headers={"stripe-signature": "t=bad,v1=bad", "content-type": "application/json"},
        )
        assert resp.status_code == 400

    def test_duplicate_event_returns_200_with_duplicate_flag(self):
        """Second POST of the SAME event payload should be accepted silently."""
        checkout_data = {
            "id": "cs_test_dup001",
            "mode": "subscription",
            "customer": "cus_dup001",
            "subscription": "sub_dup001",
            "customer_email": "dup@example.com",
        }

        # Build one fixed event envelope and send it twice
        fixed_event = {
            "id": "evt_fixed_dup_idempotency_001",
            "object": "event",
            "api_version": "2023-10-16",
            "type": "checkout.session.completed",
            "data": {"object": checkout_data},
        }

        def _post_fixed(evt: dict):
            body = json.dumps(evt).encode()
            sig  = _make_stripe_sig(body, TEST_WEBHOOK_SECRET)
            return self.client.post(
                "/billing/webhook",
                content=body,
                headers={"stripe-signature": sig, "content-type": "application/json"},
            )

        with patch.object(self.wh, "_resolve_tier_from_subscription_id",
                          return_value=(SubscriptionTier.PRO, BillingInterval.MONTHLY)):
            r1 = _post_fixed(fixed_event)
            r2 = _post_fixed(fixed_event)

        assert r1.status_code == 200
        assert r1.json().get("duplicate") is not True   # first is NOT duplicate
        assert r2.status_code == 200
        assert r2.json().get("duplicate") is True        # second IS duplicate

    def test_checkout_session_completed_creates_subscription(self):
        customer_id = "cus_newco001"
        sub_id      = "sub_newco001"
        checkout_data = {
            "id": "cs_test_001",
            "mode": "subscription",
            "customer": customer_id,
            "subscription": sub_id,
            "customer_email": "new@customer.com",
        }

        with patch.object(self.wh, "_resolve_tier_from_subscription_id",
                          return_value=(SubscriptionTier.PRO, BillingInterval.MONTHLY)):
            resp = _post_event(self.client, "checkout.session.completed", checkout_data)

        assert resp.status_code == 200
        sub = self.wh._store_instance.get_subscription_by_customer(customer_id)
        assert sub is not None
        assert sub.tier == SubscriptionTier.PRO
        assert sub.email == "new@customer.com"

    def test_checkout_non_subscription_mode_is_ignored(self):
        """Checkout sessions in 'payment' mode should be skipped."""
        resp = _post_event(self.client, "checkout.session.completed", {
            "id": "cs_pay_001",
            "mode": "payment",
            "customer": "cus_pay",
            "subscription": None,
        })
        assert resp.status_code == 200

    def test_subscription_deleted_cancels_record(self):
        cid = "cus_cancel001"
        sid = "sub_cancel001"

        # First create a subscription
        record = SubscriptionRecord(
            customer_id=cid, email="del@example.com",
            stripe_subscription_id=sid,
            tier=SubscriptionTier.ELITE,
            status=SubscriptionStatus.ACTIVE,
            interval=BillingInterval.MONTHLY,
            cancel_at_period_end=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.wh._store_instance.upsert_subscription(record)

        resp = _post_event(self.client, "customer.subscription.deleted", {
            "id": sid,
            "customer": cid,
            "cancel_at_period_end": True,
        })
        assert resp.status_code == 200
        sub = self.wh._store_instance.get_subscription_by_customer(cid)
        assert sub.status == SubscriptionStatus.CANCELED

    def test_invoice_payment_succeeded_fires_notification(self):
        cid = "cus_pay001"
        sid = "sub_pay001"

        record = SubscriptionRecord(
            customer_id=cid, email="pay@example.com",
            stripe_subscription_id=sid,
            tier=SubscriptionTier.PRO,
            status=SubscriptionStatus.ACTIVE,
            interval=BillingInterval.MONTHLY,
            cancel_at_period_end=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.wh._store_instance.upsert_subscription(record)

        resp = _post_event(self.client, "invoice.payment_succeeded", {
            "id": "in_test_001",
            "customer": cid,
            "subscription": sid,
            "amount_paid": 4900,     # $49.00
            "currency": "usd",
            "status": "paid",
        })
        assert resp.status_code == 200
        self.wh._notifier_instance.payment_succeeded.assert_called_once()

    def test_invoice_payment_failed_fires_notification(self):
        cid = "cus_fail001"
        sid = "sub_fail001"

        record = SubscriptionRecord(
            customer_id=cid, email="fail@example.com",
            stripe_subscription_id=sid,
            tier=SubscriptionTier.STARTER,
            status=SubscriptionStatus.ACTIVE,
            interval=BillingInterval.MONTHLY,
            cancel_at_period_end=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.wh._store_instance.upsert_subscription(record)

        resp = _post_event(self.client, "invoice.payment_failed", {
            "id": "in_fail_001",
            "customer": cid,
            "subscription": sid,
            "amount_due": 1900,
            "next_payment_attempt": int(time.time()) + 86400,
        })
        assert resp.status_code == 200
        self.wh._notifier_instance.payment_failed.assert_called_once()

    def test_zero_amount_invoice_skips_notification(self):
        """Free-trial invoices should not trigger payment_succeeded notification."""
        cid = "cus_free001"
        record = SubscriptionRecord(
            customer_id=cid, email="free@example.com",
            stripe_subscription_id="sub_free001",
            tier=SubscriptionTier.PRO,
            status=SubscriptionStatus.TRIALING,
            interval=BillingInterval.MONTHLY,
            cancel_at_period_end=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.wh._store_instance.upsert_subscription(record)

        resp = _post_event(self.client, "invoice.payment_succeeded", {
            "id": "in_zero_001",
            "customer": cid,
            "subscription": "sub_free001",
            "amount_paid": 0,
            "currency": "usd",
            "status": "paid",
        })
        assert resp.status_code == 200
        self.wh._notifier_instance.payment_succeeded.assert_not_called()

    def test_unhandled_event_type_returns_200(self):
        """Unknown event types should not crash the handler."""
        resp = _post_event(self.client, "unknown.event.type", {"id": "x"})
        assert resp.status_code == 200

    def test_list_subscriptions_endpoint(self):
        record = SubscriptionRecord(
            customer_id="cus_list001", email="list@example.com",
            stripe_subscription_id="sub_list001",
            tier=SubscriptionTier.TEAM,
            status=SubscriptionStatus.ACTIVE,
            interval=BillingInterval.ANNUAL,
            cancel_at_period_end=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.wh._store_instance.upsert_subscription(record)
        resp = self.client.get("/billing/subscriptions")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_customer_lookup_endpoint(self):
        record = SubscriptionRecord(
            customer_id="cus_look001", email="look@example.com",
            stripe_subscription_id="sub_look001",
            tier=SubscriptionTier.ELITE,
            status=SubscriptionStatus.ACTIVE,
            interval=BillingInterval.MONTHLY,
            cancel_at_period_end=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.wh._store_instance.upsert_subscription(record)
        resp = self.client.get("/billing/customer/cus_look001")
        assert resp.status_code == 200
        assert resp.json()["tier"] == "elite"

    def test_customer_lookup_404_for_unknown(self):
        resp = self.client.get("/billing/customer/cus_nobody_xyz")
        assert resp.status_code == 404
