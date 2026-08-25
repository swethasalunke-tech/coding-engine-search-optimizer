"""Tests for solution_optimizer.billing.stripe_webhook.

These tests build a REAL, valid-format Stripe webhook payload (matching
Stripe's publicly documented `checkout.session.completed` event shape,
https://docs.stripe.com/api/events/types#event_types-checkout.session.completed
and https://docs.stripe.com/api/checkout/sessions/object) and sign it
ourselves with `stripe.WebhookSignature.generate_signature_header` -- the
official stripe-python SDK's own helper for this, whose docstring says
"Useful for signing payloads in unit tests" (see
stripe/_webhook.py:WebhookSignature.generate_signature_header in the
installed `stripe` package). That function implements the exact same
documented HMAC-SHA256-over-"{timestamp}.{payload}" algorithm that
`stripe.Webhook.construct_event` (used inside verify_stripe_signature)
checks against. Using the SDK's own paired sign/verify helpers proves
verify_stripe_signature works against a genuinely, correctly-signed
payload -- not just that it doesn't crash on well-formed input.

NO real Stripe API key or webhook secret is used anywhere in this file.
TEST_WEBHOOK_SECRET below is a string chosen for this test suite only; it
has never been registered with Stripe, and no network call is made to
Stripe (or anywhere else) by any test here.
"""

import json

import pytest
import stripe

from solution_optimizer.billing.stripe_webhook import create_app
from solution_optimizer.license.keys import generate_keypair, verify_license

TEST_WEBHOOK_SECRET = "whsec_test_placeholder_do_not_use_live"
TEST_PRICE_ID = "price_TEST_placeholder_001"


def _checkout_session(include_line_items=True, price_id=TEST_PRICE_ID, session_id="cs_test_a1B2c3D4e5F6g7H8i9J0"):
    session = {
        "id": session_id,
        "object": "checkout.session",
        "amount_subtotal": 4900,
        "amount_total": 4900,
        "currency": "usd",
        "customer": "cus_TESTfakecustomer1",
        "customer_email": "test-customer@example.com",
        "livemode": False,
        "metadata": {},
        "mode": "payment",
        "payment_intent": "pi_TESTfakepaymentintent1",
        "payment_status": "paid",
        "status": "complete",
        "success_url": "https://example.com/success",
        "cancel_url": "https://example.com/cancel",
    }
    if include_line_items:
        session["line_items"] = {
            "object": "list",
            "data": [
                {
                    "id": "li_TESTfakelineitem1",
                    "object": "item",
                    "price": {"id": price_id, "object": "price", "currency": "usd"},
                    "quantity": 1,
                }
            ],
            "has_more": False,
        }
    return session


def _event(event_type="checkout.session.completed", session=None):
    return {
        "id": "evt_TESTfakeevent1",
        "object": "event",
        "api_version": "2024-06-20",
        "created": 1700000000,
        "livemode": False,
        "pending_webhooks": 1,
        "request": {"id": None, "idempotency_key": None},
        "type": event_type,
        "data": {"object": session if session is not None else _checkout_session()},
    }


def _signed_request(payload_dict, secret=TEST_WEBHOOK_SECRET):
    """Serialize payload_dict to the exact bytes we'll POST, and compute a
    real Stripe-Signature header for those exact bytes using the stripe
    SDK's own documented test-signing helper."""
    body = json.dumps(payload_dict)
    header = stripe.WebhookSignature.generate_signature_header(body, secret)
    return body.encode("utf-8"), header


@pytest.fixture()
def keypair():
    return generate_keypair()


@pytest.fixture()
def price_tier_map():
    return {
        TEST_PRICE_ID: {
            "tier": "pro",
            "features": ["org_dashboard"],
            "duration_days": 365,
        }
    }


@pytest.fixture()
def client(keypair, price_tier_map):
    private_key, _public_key = keypair
    app = create_app(TEST_WEBHOOK_SECRET, price_tier_map, private_key)
    app.config.update(TESTING=True)
    return app.test_client()


def test_valid_signature_and_known_price_issues_verifiable_license(client, keypair):
    """Round-trips through both billing (issuance) and license (verify)
    modules: POST a correctly-signed checkout.session.completed event,
    get a 200 with a license_token, and verify that token with day-1's
    verify_license against the same keypair."""
    _private_key, public_key = keypair
    body, header = _signed_request(_event())

    response = client.post(
        "/webhooks/stripe",
        data=body,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "license_token" in data
    token = data["license_token"]

    recovered = verify_license(token, public_key)
    assert recovered["tier"] == "pro"
    assert recovered["features"] == ["org_dashboard"]
    assert recovered["stripe_price_id"] == TEST_PRICE_ID
    assert recovered["stripe_checkout_session_id"] == "cs_test_a1B2c3D4e5F6g7H8i9J0"


def test_tampered_payload_rejected(client):
    """Sign one payload, then send different bytes under that same
    signature header -- the HMAC won't match the (different) body, so
    this must be rejected exactly like a real tampered webhook would be."""
    body, header = _signed_request(_event())
    tampered_body = body.replace(b'"paid"', b'"unpaid"')
    assert tampered_body != body

    response = client.post(
        "/webhooks/stripe",
        data=tampered_body,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_wrong_webhook_secret_rejected(client):
    """Signed with a different secret than the app is configured with --
    the app must never accept a signature computed under the wrong
    secret."""
    body, header = _signed_request(_event(), secret="whsec_totally_different_test_secret")

    response = client.post(
        "/webhooks/stripe",
        data=body,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_missing_signature_header_rejected(client):
    body = json.dumps(_event()).encode("utf-8")

    response = client.post(
        "/webhooks/stripe",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_ignored_event_type_returns_200(client):
    body, header = _signed_request(_event(event_type="invoice.paid", session={"id": "in_TESTfakeinvoice1"}))

    response = client.post(
        "/webhooks/stripe",
        data=body,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "ignored" in data["status"]
    assert data["type"] == "invoice.paid"


def test_unknown_price_id_returns_422(client):
    session = _checkout_session(price_id="price_TEST_not_in_map")
    body, header = _signed_request(_event(session=session))

    response = client.post(
        "/webhooks/stripe",
        data=body,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "error" in response.get_json()


def test_missing_line_items_returns_422(client):
    session = _checkout_session(include_line_items=False)
    body, header = _signed_request(_event(session=session))

    response = client.post(
        "/webhooks/stripe",
        data=body,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "line_items" in response.get_json()["error"]
