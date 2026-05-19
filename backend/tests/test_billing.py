"""Tests for billing endpoints and subscription service.

Strategy:
- billing router is only registered when STRIPE_ENABLED=true, so tests
  toggle the setting and patch stripe SDK calls.
- Webhook signature verification is patched to avoid real Stripe keys.
- All Stripe API calls are mocked so no real network requests are made.
"""
from __future__ import annotations

import json
import stripe
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from app.core.config import settings
from app.main import app
from app.services.subscription_service import is_subscribed

# Register the billing router once for the entire test module so routes are
# available without re-registering on every test (which causes duplicates).
from app.routers import billing as _billing_module

_BILLING_ROUTES = {getattr(r, "path", None) for r in app.routes}
if "/api/billing/checkout" not in _BILLING_ROUTES:
    app.include_router(_billing_module.router)


def _signed_webhook_headers() -> dict:
    """Return fake Stripe-Signature header (signature check is mocked)."""
    return {
        "stripe-signature": "t=1,v1=fakesig",
        "content-type": "application/json",
    }


# ── subscription_service.is_subscribed ───────────────────────────────────────

class TestIsSubscribed:
    def test_stripe_disabled_always_true(self):
        user = MagicMock()
        user.subscription_status = "none"
        assert is_subscribed(user, stripe_enabled=False) is True

    def test_active_user_subscribed(self):
        user = MagicMock()
        user.subscription_status = "active"
        assert is_subscribed(user, stripe_enabled=True) is True

    def test_trialing_user_subscribed(self):
        user = MagicMock()
        user.subscription_status = "trialing"
        assert is_subscribed(user, stripe_enabled=True) is True

    def test_none_user_not_subscribed(self):
        user = MagicMock()
        user.subscription_status = "none"
        assert is_subscribed(user, stripe_enabled=True) is False

    def test_canceled_user_not_subscribed(self):
        user = MagicMock()
        user.subscription_status = "canceled"
        assert is_subscribed(user, stripe_enabled=True) is False

    def test_past_due_user_not_subscribed(self):
        user = MagicMock()
        user.subscription_status = "past_due"
        assert is_subscribed(user, stripe_enabled=True) is False


# ── GET /api/config ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_config_stripe_disabled(client):
    with patch.object(settings, "STRIPE_ENABLED", False):
        res = await client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert data["stripe_enabled"] is False
    assert "stripe_trial_days" in data


@pytest.mark.asyncio
async def test_config_stripe_enabled(client):
    with patch.object(settings, "STRIPE_ENABLED", True):
        res = await client.get("/api/config")
    assert res.status_code == 200
    assert res.json()["stripe_enabled"] is True


# ── require_subscription dependency ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_require_subscription_blocks_when_stripe_enabled(client, test_user):
    """Unsubscribed user gets HTTP 402 when STRIPE_ENABLED=true."""
    user, headers = test_user
    with patch.object(settings, "STRIPE_ENABLED", True):
        res = await client.get("/api/chat/conversations", headers=headers)
    assert res.status_code == 402
    assert res.json()["detail"] == "subscription_required"


@pytest.mark.asyncio
async def test_require_subscription_passes_when_stripe_disabled(client, test_user):
    """All users pass when STRIPE_ENABLED=false (self-hosted)."""
    _, headers = test_user
    with patch.object(settings, "STRIPE_ENABLED", False):
        res = await client.get("/api/chat/conversations", headers=headers)
    # Any non-402 response means the paywall was bypassed
    assert res.status_code != 402


@pytest.mark.asyncio
async def test_require_subscription_passes_for_active_user(client, db_session, test_user):
    """Active subscriber can access protected endpoints."""
    user, headers = test_user
    user.subscription_status = "active"
    await db_session.commit()

    with patch.object(settings, "STRIPE_ENABLED", True):
        res = await client.get("/api/chat/conversations", headers=headers)
    assert res.status_code != 402


# ── POST /api/billing/checkout ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_checkout_monthly(client, test_user):
    """Creates a Checkout session for the monthly plan."""
    _, headers = test_user

    mock_customer = MagicMock()
    mock_customer.id = "cus_test123"
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/test"

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch.object(settings, "STRIPE_PRICE_MONTHLY", "price_monthly_test"),
        patch.object(settings, "STRIPE_PRICE_YEARLY", "price_yearly_test"),
        patch("stripe.Customer.create", return_value=mock_customer),
        patch("stripe.checkout.Session.create", return_value=mock_session),
    ):
        res = await client.post(
            "/api/billing/checkout",
            json={"plan": "monthly"},
            headers=headers,
        )

    assert res.status_code == 200
    assert res.json()["url"] == "https://checkout.stripe.com/pay/test"


@pytest.mark.asyncio
async def test_checkout_yearly(client, test_user):
    """Creates a Checkout session for the yearly plan."""
    _, headers = test_user

    mock_customer = MagicMock()
    mock_customer.id = "cus_test456"
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/yearly_test"

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch.object(settings, "STRIPE_PRICE_MONTHLY", "price_monthly_test"),
        patch.object(settings, "STRIPE_PRICE_YEARLY", "price_yearly_test"),
        patch("stripe.Customer.create", return_value=mock_customer),
        patch("stripe.checkout.Session.create", return_value=mock_session),
    ):
        res = await client.post(
            "/api/billing/checkout",
            json={"plan": "yearly"},
            headers=headers,
        )

    assert res.status_code == 200
    assert res.json()["url"] == "https://checkout.stripe.com/pay/yearly_test"


@pytest.mark.asyncio
async def test_checkout_missing_price_config(client, test_user):
    """Returns 503 when Stripe prices are not configured."""
    _, headers = test_user

    mock_customer = MagicMock()
    mock_customer.id = "cus_test789"

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch.object(settings, "STRIPE_PRICE_MONTHLY", ""),
        patch.object(settings, "STRIPE_PRICE_YEARLY", ""),
        patch("stripe.Customer.create", return_value=mock_customer),
    ):
        res = await client.post(
            "/api/billing/checkout",
            json={"plan": "monthly"},
            headers=headers,
        )

    assert res.status_code == 503


# ── POST /api/billing/webhook ─────────────────────────────────────────────────

def _make_stripe_event(event_type: str, data: dict) -> dict:
    """Build a minimal Stripe event envelope for webhook tests."""
    return {"type": event_type, "data": {"object": data}}


def _make_webhook_body(event: dict) -> bytes:
    return json.dumps(event).encode()


@pytest.mark.asyncio
async def test_webhook_checkout_completed_activates_subscription(client, db_session, test_user):
    """checkout.session.completed → subscription_status set to 'trialing'."""
    user, _ = test_user
    user.stripe_customer_id = "cus_webhook1"
    await db_session.commit()

    event = _make_stripe_event(
        "checkout.session.completed",
        {
            "customer": "cus_webhook1",
            "subscription": "sub_test1",
            "metadata": {"user_id": str(user.id)},
        },
    )

    mock_sub = MagicMock()
    mock_sub.status = "trialing"
    mock_sub.get.return_value = int(datetime(2026, 12, 31).timestamp())

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch("stripe.Webhook.construct_event", return_value=event),
        patch("stripe.Subscription.retrieve", return_value=mock_sub),
    ):
        res = await client.post(
            "/api/billing/webhook",
            content=_make_webhook_body(event),
            headers=_signed_webhook_headers(),
        )

    assert res.status_code == 200
    await db_session.refresh(user)
    assert user.subscription_status == "trialing"


@pytest.mark.asyncio
async def test_webhook_subscription_updated(client, db_session, test_user):
    """customer.subscription.updated → subscription_status updated."""
    user, _ = test_user
    user.stripe_customer_id = "cus_webhook2"
    user.subscription_status = "trialing"
    await db_session.commit()

    event = _make_stripe_event(
        "customer.subscription.updated",
        {
            "customer": "cus_webhook2",
            "status": "active",
            "current_period_end": int(datetime(2027, 1, 31).timestamp()),
        },
    )

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch("stripe.Webhook.construct_event", return_value=event),
    ):
        res = await client.post(
            "/api/billing/webhook",
            content=_make_webhook_body(event),
            headers=_signed_webhook_headers(),
        )

    assert res.status_code == 200
    await db_session.refresh(user)
    assert user.subscription_status == "active"


@pytest.mark.asyncio
async def test_webhook_subscription_deleted(client, db_session, test_user):
    """customer.subscription.deleted → subscription_status set to 'canceled'."""
    user, _ = test_user
    user.stripe_customer_id = "cus_webhook3"
    user.subscription_status = "active"
    await db_session.commit()

    event = _make_stripe_event(
        "customer.subscription.deleted",
        {"customer": "cus_webhook3"},
    )

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch("stripe.Webhook.construct_event", return_value=event),
    ):
        res = await client.post(
            "/api/billing/webhook",
            content=_make_webhook_body(event),
            headers=_signed_webhook_headers(),
        )

    assert res.status_code == 200
    await db_session.refresh(user)
    assert user.subscription_status == "canceled"


@pytest.mark.asyncio
async def test_webhook_invoice_payment_failed(client, db_session, test_user):
    """invoice.payment_failed → subscription_status set to 'past_due'."""
    user, _ = test_user
    user.stripe_customer_id = "cus_webhook4"
    user.subscription_status = "active"
    await db_session.commit()

    event = _make_stripe_event(
        "invoice.payment_failed",
        {"customer": "cus_webhook4"},
    )

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch("stripe.Webhook.construct_event", return_value=event),
    ):
        res = await client.post(
            "/api/billing/webhook",
            content=_make_webhook_body(event),
            headers=_signed_webhook_headers(),
        )

    assert res.status_code == 200
    await db_session.refresh(user)
    assert user.subscription_status == "past_due"


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(client):
    """Webhook with bad signature → HTTP 400."""
    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.SignatureVerificationError("bad sig", "sig_header"),
        ),
    ):
        res = await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers=_signed_webhook_headers(),
        )

    assert res.status_code == 400
    assert "signature" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_invalid_payload_rejected(client):
    """Webhook with malformed payload → HTTP 400."""
    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch("stripe.Webhook.construct_event", side_effect=ValueError("bad payload")),
    ):
        res = await client.post(
            "/api/billing/webhook",
            content=b"not-json",
            headers=_signed_webhook_headers(),
        )

    assert res.status_code == 400
    assert "payload" in res.json()["detail"].lower()
