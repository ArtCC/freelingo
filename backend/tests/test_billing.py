"""Tests for billing endpoints and subscription service.

Strategy:
- billing router is only registered when STRIPE_ENABLED=true, so tests
  toggle the setting and patch stripe SDK calls.
- Webhook signature verification is patched to avoid real Stripe keys.
- All Stripe API calls are mocked so no real network requests are made.
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import stripe

from app.core.config import settings
from app.main import app

# Register the billing router once for the entire test module so routes are
# available without re-registering on every test (which causes duplicates).
from app.routers import billing as _billing_module
from app.services.subscription_service import is_subscribed

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

    @pytest.mark.parametrize(
        "stripe_status", ["incomplete", "incomplete_expired", "unpaid", "paused"]
    )
    def test_other_stripe_statuses_not_subscribed(self, stripe_status):
        user = MagicMock()
        user.subscription_status = stripe_status
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
async def test_require_subscription_blocks_when_stripe_enabled(client, test_user_with_plan):
    """Unsubscribed user gets HTTP 200 when STRIPE_ENABLED=true (freemium quotas allow access)."""
    user, headers = test_user_with_plan
    with patch.object(settings, "STRIPE_ENABLED", True):
        res = await client.get("/api/chat/conversations", headers=headers)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_require_subscription_passes_when_stripe_disabled(client, test_user_with_plan):
    """All users pass when STRIPE_ENABLED=false (self-hosted)."""
    _, headers = test_user_with_plan
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


@pytest.mark.asyncio
async def test_checkout_reuses_existing_customer(client, db_session, test_user):
    """Existing Stripe customers are reused instead of creating duplicates."""
    user, headers = test_user
    user.stripe_customer_id = "cus_existing"
    await db_session.commit()

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/existing"

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch.object(settings, "STRIPE_PRICE_MONTHLY", "price_monthly_test"),
        patch.object(settings, "STRIPE_PRICE_YEARLY", "price_yearly_test"),
        patch("stripe.Customer.create") as mock_create_customer,
        patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create_session,
    ):
        res = await client.post(
            "/api/billing/checkout",
            json={"plan": "monthly"},
            headers=headers,
        )

    assert res.status_code == 200
    assert res.json()["url"] == "https://checkout.stripe.com/pay/existing"
    mock_create_customer.assert_not_called()
    assert mock_create_session.call_args.kwargs["customer"] == "cus_existing"


# ── POST /api/billing/portal ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_portal_opens_for_past_due_user(client, db_session, test_user):
    """past_due users can open Customer Portal to repair the payment."""
    user, headers = test_user
    user.stripe_customer_id = "cus_past_due"
    user.subscription_status = "past_due"
    await db_session.commit()

    mock_session = MagicMock()
    mock_session.url = "https://billing.stripe.com/session/test"

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch("stripe.billing_portal.Session.create", return_value=mock_session) as mock_portal,
    ):
        res = await client.post("/api/billing/portal", headers=headers)

    assert res.status_code == 200
    assert res.json()["url"] == "https://billing.stripe.com/session/test"
    assert mock_portal.call_args.kwargs["customer"] == "cus_past_due"


@pytest.mark.asyncio
async def test_portal_requires_existing_customer(client, test_user):
    """Users without a Stripe customer cannot open the Customer Portal."""
    _, headers = test_user

    with patch.object(settings, "STRIPE_ENABLED", True):
        res = await client.post("/api/billing/portal", headers=headers)

    assert res.status_code == 400
    assert res.json()["detail"] == "No active subscription found"


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
        patch(
            "stripe.Subscription.retrieve_async",
            new_callable=AsyncMock,
            return_value=mock_sub,
        ),
    ):
        res = await client.post(
            "/api/billing/webhook",
            content=_make_webhook_body(event),
            headers=_signed_webhook_headers(),
        )

    assert res.status_code == 200
    await db_session.refresh(user)
    assert user.subscription_status == "trialing"
    assert user.stripe_subscription_id == "sub_test1"


@pytest.mark.asyncio
async def test_webhook_checkout_completed_retries_when_subscription_lookup_fails(
    client, db_session, test_user
):
    """checkout.session.completed returns 500 if the subscription cannot be verified."""
    user, _ = test_user
    user.stripe_customer_id = "cus_lookup_fail"
    user.subscription_status = "none"
    await db_session.commit()

    event = _make_stripe_event(
        "checkout.session.completed",
        {
            "customer": "cus_lookup_fail",
            "subscription": "sub_lookup_fail",
            "metadata": {"user_id": str(user.id)},
        },
    )

    with (
        patch.object(settings, "STRIPE_ENABLED", True),
        patch("stripe.Webhook.construct_event", return_value=event),
        patch(
            "stripe.Subscription.retrieve_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("stripe unavailable"),
        ),
    ):
        res = await client.post(
            "/api/billing/webhook",
            content=_make_webhook_body(event),
            headers=_signed_webhook_headers(),
        )

    assert res.status_code == 500
    await db_session.refresh(user)
    assert user.subscription_status == "none"


@pytest.mark.asyncio
async def test_webhook_subscription_updated(client, db_session, test_user):
    """customer.subscription.updated → subscription_status updated."""
    user, _ = test_user
    user.stripe_customer_id = "cus_webhook2"
    user.stripe_subscription_id = "sub_current"
    user.subscription_status = "trialing"
    await db_session.commit()

    event = _make_stripe_event(
        "customer.subscription.updated",
        {
            "id": "sub_current",
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
async def test_webhook_subscription_updated_ignores_stale_subscription(
    client, db_session, test_user
):
    """customer.subscription.updated from an old subscription does not change state."""
    user, _ = test_user
    user.stripe_customer_id = "cus_stale_update"
    user.stripe_subscription_id = "sub_current"
    user.subscription_status = "active"
    await db_session.commit()

    event = _make_stripe_event(
        "customer.subscription.updated",
        {
            "id": "sub_old",
            "customer": "cus_stale_update",
            "status": "canceled",
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
    assert user.stripe_subscription_id == "sub_current"


@pytest.mark.asyncio
async def test_webhook_subscription_updated_binds_missing_subscription_id(
    client, db_session, test_user
):
    """Existing users without stripe_subscription_id are backfilled from updates."""
    user, _ = test_user
    user.stripe_customer_id = "cus_bind_update"
    user.stripe_subscription_id = None
    user.subscription_status = "trialing"
    await db_session.commit()

    event = _make_stripe_event(
        "customer.subscription.updated",
        {
            "id": "sub_bound",
            "customer": "cus_bind_update",
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
    assert user.stripe_subscription_id == "sub_bound"


@pytest.mark.asyncio
@pytest.mark.parametrize("stripe_status", ["incomplete", "incomplete_expired", "unpaid", "paused"])
async def test_webhook_subscription_updated_accepts_real_stripe_statuses(
    client, db_session, test_user, stripe_status
):
    """customer.subscription.updated persists real Stripe statuses used for UI labels."""
    user, _ = test_user
    user.stripe_customer_id = f"cus_{stripe_status}"
    user.subscription_status = "active"
    await db_session.commit()

    event = _make_stripe_event(
        "customer.subscription.updated",
        {
            "customer": f"cus_{stripe_status}",
            "status": stripe_status,
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
    assert user.subscription_status == stripe_status


@pytest.mark.asyncio
async def test_webhook_subscription_updated_unknown_status_keeps_existing_status(
    client, db_session, test_user
):
    """Unknown Stripe statuses are not persisted into the closed UI model."""
    user, _ = test_user
    user.stripe_customer_id = "cus_unknown_status"
    user.subscription_status = "past_due"
    await db_session.commit()

    event = _make_stripe_event(
        "customer.subscription.updated",
        {"customer": "cus_unknown_status", "status": "unexpected_status"},
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
async def test_webhook_subscription_deleted(client, db_session, test_user):
    """customer.subscription.deleted → subscription_status set to 'canceled'."""
    user, _ = test_user
    user.stripe_customer_id = "cus_webhook3"
    user.stripe_subscription_id = "sub_deleted"
    user.subscription_status = "active"
    await db_session.commit()

    event = _make_stripe_event(
        "customer.subscription.deleted",
        {"id": "sub_deleted", "customer": "cus_webhook3"},
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
async def test_webhook_subscription_deleted_ignores_stale_subscription(
    client, db_session, test_user
):
    """customer.subscription.deleted from an old subscription does not cancel access."""
    user, _ = test_user
    user.stripe_customer_id = "cus_stale_delete"
    user.stripe_subscription_id = "sub_current"
    user.subscription_status = "active"
    await db_session.commit()

    event = _make_stripe_event(
        "customer.subscription.deleted",
        {"id": "sub_old", "customer": "cus_stale_delete"},
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
async def test_webhook_invoice_payment_failed(client, db_session, test_user):
    """invoice.payment_failed → subscription_status set to 'past_due'."""
    user, _ = test_user
    user.stripe_customer_id = "cus_webhook4"
    user.stripe_subscription_id = "sub_failed"
    user.subscription_status = "active"
    await db_session.commit()

    event = _make_stripe_event(
        "invoice.payment_failed",
        {"customer": "cus_webhook4", "subscription": "sub_failed"},
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
async def test_webhook_invoice_payment_failed_uses_current_invoice_parent_shape(
    client, db_session, test_user
):
    """invoice.payment_failed reads subscription from parent.subscription_details."""
    user, _ = test_user
    user.stripe_customer_id = "cus_invoice_parent"
    user.stripe_subscription_id = "sub_parent"
    user.subscription_status = "active"
    await db_session.commit()

    event = _make_stripe_event(
        "invoice.payment_failed",
        {
            "customer": "cus_invoice_parent",
            "parent": {"subscription_details": {"subscription": "sub_parent"}},
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
    assert user.subscription_status == "past_due"


@pytest.mark.asyncio
async def test_webhook_invoice_payment_failed_ignores_stale_subscription(
    client, db_session, test_user
):
    """invoice.payment_failed from an old subscription does not mark past_due."""
    user, _ = test_user
    user.stripe_customer_id = "cus_stale_invoice"
    user.stripe_subscription_id = "sub_current"
    user.subscription_status = "active"
    await db_session.commit()

    event = _make_stripe_event(
        "invoice.payment_failed",
        {"customer": "cus_stale_invoice", "subscription": "sub_old"},
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
async def test_webhook_invoice_payment_failed_ignores_stale_parent_subscription(
    client, db_session, test_user
):
    """Current Invoice shape still ignores old subscription failures."""
    user, _ = test_user
    user.stripe_customer_id = "cus_stale_invoice_parent"
    user.stripe_subscription_id = "sub_current"
    user.subscription_status = "active"
    await db_session.commit()

    event = _make_stripe_event(
        "invoice.payment_failed",
        {
            "customer": "cus_stale_invoice_parent",
            "parent": {"subscription_details": {"subscription": "sub_old"}},
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
