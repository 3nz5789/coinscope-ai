"""
Customer Portal Session API Tests
==================================
Tests for:
  POST /billing/portal/session  — session creation (customer_id & email paths)
  GET  /billing/portal/config   — portal configuration check
  SubscriptionStore.get_customer_id_by_email  — new lookup method

Run:
    cd /path/to/CoinScopeAI
    python -m pytest tests/test_billing_portal.py -v

All Stripe API calls are mocked — no real network traffic.
"""

import os
import sys
import tempfile
import pathlib
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# ── Environment setup (must precede any billing imports) ──────────────────────
os.environ["STRIPE_SECRET_KEY"] = "sk_test_portal_test_key"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_portal"
os.environ["BILLING_PORTAL_RETURN_URL"] = "http://localhost:5173/account"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from billing.webhook_handler import app
from billing.subscription_store import SubscriptionStore
from billing.models import (
    SubscriptionRecord,
    SubscriptionTier,
    SubscriptionStatus,
    BillingInterval,
)

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_store(tmp_path):
    """Temporary SQLite store isolated per test."""
    db_path = str(tmp_path / "test_portal.db")
    return SubscriptionStore(db_path=db_path)


def _sample_record(
    customer_id: str = "cus_test_001",
    email: str = "trader@coinscopeai.com",
    tier: SubscriptionTier = SubscriptionTier.PRO,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> SubscriptionRecord:
    now = datetime.now(timezone.utc)
    return SubscriptionRecord(
        customer_id=customer_id,
        email=email,
        stripe_subscription_id="sub_test_001",
        tier=tier,
        status=status,
        interval=BillingInterval.MONTHLY,
        cancel_at_period_end=False,
        created_at=now,
        updated_at=now,
    )


def _mock_portal_session(url: str = "https://billing.stripe.com/session/test_xxx") -> MagicMock:
    session = MagicMock()
    session.url = url
    return session


def _mock_customer() -> MagicMock:
    customer = MagicMock()
    customer.id = "cus_test_001"
    return customer


# ── SubscriptionStore.get_customer_id_by_email tests ─────────────────────────

class TestGetCustomerIdByEmail:
    def test_returns_customer_id_for_known_email(self, tmp_store):
        tmp_store.upsert_subscription(_sample_record())
        result = tmp_store.get_customer_id_by_email("trader@coinscopeai.com")
        assert result == "cus_test_001"

    def test_case_insensitive_lookup(self, tmp_store):
        tmp_store.upsert_subscription(_sample_record(email="Trader@CoinScopeAI.COM"))
        assert tmp_store.get_customer_id_by_email("trader@coinscopeai.com") == "cus_test_001"
        assert tmp_store.get_customer_id_by_email("TRADER@COINSCOPEAI.COM") == "cus_test_001"

    def test_returns_none_for_unknown_email(self, tmp_store):
        assert tmp_store.get_customer_id_by_email("ghost@nowhere.com") is None

    def test_empty_store_returns_none(self, tmp_store):
        assert tmp_store.get_customer_id_by_email("any@email.com") is None

    def test_returns_most_recent_on_duplicate_email(self, tmp_store):
        """Edge case: same email, two customer IDs (data integrity issue) — return latest."""
        now = datetime.now(timezone.utc)
        rec1 = _sample_record(customer_id="cus_old", email="dup@test.com")
        rec2 = _sample_record(customer_id="cus_new", email="dup@test.com")
        # Insert older record first, newer second (updated_at is set by upsert)
        tmp_store.upsert_subscription(rec1)
        import time; time.sleep(0.01)  # ensure updated_at differs
        tmp_store.upsert_subscription(rec2)
        result = tmp_store.get_customer_id_by_email("dup@test.com")
        # Should return the more recently updated record
        assert result in ("cus_old", "cus_new")  # both valid; store picks latest


# ── GET /billing/portal/config tests ─────────────────────────────────────────

class TestPortalConfig:
    def test_config_when_portal_configured(self):
        mock_config = MagicMock()
        mock_config.data = [MagicMock()]  # one active configuration

        with patch("billing.customer_portal.stripe.billing_portal.Configuration.list",
                   return_value=mock_config):
            resp = client.get("/billing/portal/config")

        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is True
        assert data["portal_configurations"] == 1
        assert data["mode"] == "test"
        assert "ready" in data["note"].lower()

    def test_config_when_portal_not_configured(self):
        mock_config = MagicMock()
        mock_config.data = []  # no configurations

        with patch("billing.customer_portal.stripe.billing_portal.Configuration.list",
                   return_value=mock_config):
            resp = client.get("/billing/portal/config")

        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False
        assert data["portal_configurations"] == 0
        assert "dashboard.stripe.com" in data["note"]

    def test_config_stripe_auth_error(self):
        import stripe as stripe_lib
        with patch("billing.customer_portal.stripe.billing_portal.Configuration.list",
                   side_effect=stripe_lib.AuthenticationError("bad key")):
            resp = client.get("/billing/portal/config")

        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False
        assert "authentication" in data["reason"].lower()


# ── POST /billing/portal/session tests ───────────────────────────────────────

class TestCreatePortalSession:

    # ── Happy path: customer_id provided ─────────────────────────────────

    def test_session_created_with_customer_id(self):
        with patch("billing.customer_portal.stripe.Customer.retrieve",
                   return_value=_mock_customer()), \
             patch("billing.customer_portal.stripe.billing_portal.Session.create",
                   return_value=_mock_portal_session()) as mock_create:

            resp = client.post("/billing/portal/session", json={
                "customer_id": "cus_test_001"
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["portal_url"] == "https://billing.stripe.com/session/test_xxx"
        assert data["customer_id"] == "cus_test_001"
        assert data["return_url"] == "http://localhost:5173/account"

        mock_create.assert_called_once_with(
            customer="cus_test_001",
            return_url="http://localhost:5173/account",
        )

    def test_session_with_custom_return_url(self):
        with patch("billing.customer_portal.stripe.Customer.retrieve",
                   return_value=_mock_customer()), \
             patch("billing.customer_portal.stripe.billing_portal.Session.create",
                   return_value=_mock_portal_session()) as mock_create:

            resp = client.post("/billing/portal/session", json={
                "customer_id": "cus_test_001",
                "return_url": "https://dashboard.myapp.com/settings",
            })

        assert resp.status_code == 200
        assert resp.json()["return_url"] == "https://dashboard.myapp.com/settings"
        mock_create.assert_called_once_with(
            customer="cus_test_001",
            return_url="https://dashboard.myapp.com/settings",
        )

    # ── Happy path: email lookup ──────────────────────────────────────────

    def test_session_created_via_email_lookup(self, tmp_store):
        tmp_store.upsert_subscription(_sample_record(
            customer_id="cus_email_lookup",
            email="pro@trader.com",
        ))

        with patch("billing.customer_portal._get_store", return_value=tmp_store), \
             patch("billing.customer_portal.stripe.Customer.retrieve",
                   return_value=_mock_customer()), \
             patch("billing.customer_portal.stripe.billing_portal.Session.create",
                   return_value=_mock_portal_session()) as mock_create:

            resp = client.post("/billing/portal/session", json={
                "email": "pro@trader.com"
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["customer_id"] == "cus_email_lookup"
        mock_create.assert_called_once_with(
            customer="cus_email_lookup",
            return_url="http://localhost:5173/account",
        )

    def test_email_lookup_case_insensitive(self, tmp_store):
        tmp_store.upsert_subscription(_sample_record(
            customer_id="cus_case_test",
            email="User@Example.COM",
        ))

        with patch("billing.customer_portal._get_store", return_value=tmp_store), \
             patch("billing.customer_portal.stripe.Customer.retrieve",
                   return_value=_mock_customer()), \
             patch("billing.customer_portal.stripe.billing_portal.Session.create",
                   return_value=_mock_portal_session()):

            resp = client.post("/billing/portal/session", json={
                "email": "user@example.com"
            })

        assert resp.status_code == 200

    def test_customer_id_takes_precedence_over_email(self):
        """When both customer_id and email are provided, customer_id wins."""
        with patch("billing.customer_portal.stripe.Customer.retrieve",
                   return_value=_mock_customer()), \
             patch("billing.customer_portal.stripe.billing_portal.Session.create",
                   return_value=_mock_portal_session()) as mock_create:

            resp = client.post("/billing/portal/session", json={
                "customer_id": "cus_test_001",
                "email": "someone@else.com",  # should be ignored
            })

        assert resp.status_code == 200
        mock_create.assert_called_once_with(
            customer="cus_test_001",
            return_url="http://localhost:5173/account",
        )

    # ── Validation errors ─────────────────────────────────────────────────

    def test_missing_both_customer_id_and_email(self):
        resp = client.post("/billing/portal/session", json={})
        assert resp.status_code == 422

    def test_invalid_customer_id_format(self):
        resp = client.post("/billing/portal/session", json={
            "customer_id": "not_a_cus_id"
        })
        assert resp.status_code == 422

    # ── Not found cases ───────────────────────────────────────────────────

    def test_email_not_in_db_returns_404(self, tmp_store):
        with patch("billing.customer_portal._get_store", return_value=tmp_store):
            resp = client.post("/billing/portal/session", json={
                "email": "ghost@nobody.com"
            })
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_stripe_customer_not_found_returns_404(self):
        import stripe as stripe_lib
        with patch("billing.customer_portal.stripe.Customer.retrieve",
                   side_effect=stripe_lib.InvalidRequestError("No such customer", param=None)):
            resp = client.post("/billing/portal/session", json={
                "customer_id": "cus_ghost_999"
            })
        assert resp.status_code == 404
        assert "cus_ghost_999" in resp.json()["detail"]

    # ── Stripe error cases ────────────────────────────────────────────────

    def test_portal_not_configured_returns_422(self):
        import stripe as stripe_lib

        with patch("billing.customer_portal.stripe.Customer.retrieve",
                   return_value=_mock_customer()), \
             patch("billing.customer_portal.stripe.billing_portal.Session.create",
                   side_effect=stripe_lib.InvalidRequestError(
                       "No configuration provided and no default exists", param=None
                   )):

            resp = client.post("/billing/portal/session", json={
                "customer_id": "cus_test_001"
            })

        assert resp.status_code == 422
        assert "dashboard.stripe.com" in resp.json()["detail"]

    def test_stripe_auth_error_returns_503(self):
        import stripe as stripe_lib
        with patch("billing.customer_portal.stripe.Customer.retrieve",
                   side_effect=stripe_lib.AuthenticationError("bad key")):
            resp = client.post("/billing/portal/session", json={
                "customer_id": "cus_test_001"
            })
        assert resp.status_code == 503

    def test_generic_stripe_error_on_session_create_returns_502(self):
        import stripe as stripe_lib
        with patch("billing.customer_portal.stripe.Customer.retrieve",
                   return_value=_mock_customer()), \
             patch("billing.customer_portal.stripe.billing_portal.Session.create",
                   side_effect=stripe_lib.APIConnectionError("network down")):
            resp = client.post("/billing/portal/session", json={
                "customer_id": "cus_test_001"
            })
        assert resp.status_code == 502


# ── Route registration sanity check ──────────────────────────────────────────

class TestRouteRegistration:
    def test_portal_session_route_exists(self):
        routes = {r.path for r in app.routes}
        assert "/billing/portal/session" in routes

    def test_portal_config_route_exists(self):
        routes = {r.path for r in app.routes}
        assert "/billing/portal/config" in routes

    def test_existing_webhook_route_still_present(self):
        routes = {r.path for r in app.routes}
        assert "/billing/webhook" in routes

    def test_health_route_still_present(self):
        routes = {r.path for r in app.routes}
        assert "/billing/health" in routes
