"""Tests for solution_optimizer.billing.license_issuer.

No live Stripe API call is made anywhere in this file. These tests build
plain dicts shaped like the Checkout Session object Stripe documents at
https://docs.stripe.com/api/checkout/sessions/object (and embeds as
data.object inside a checkout.session.completed event), and pass them
directly into issue_license_for_checkout_session -- there is no network
involved at all.
"""

from datetime import datetime, timezone

import pytest

from solution_optimizer.billing.license_issuer import (
    DEFAULT_PRICE_TIER_MAP,
    MissingLineItemsError,
    UnknownPriceError,
    issue_license_for_checkout_session,
)
from solution_optimizer.license.keys import generate_keypair, verify_license

# A test-only placeholder Price ID -- deliberately NOT shaped to look like
# a real Stripe Price ID (real ones look like "price_1AbCDeFgHiJkLmNoPq").
# This is a key we chose ourselves for this map in this test file only.
TEST_PRICE_ID = "price_TEST_placeholder_001"


@pytest.fixture()
def keypair():
    return generate_keypair()


@pytest.fixture()
def price_tier_map():
    return {
        TEST_PRICE_ID: {
            "tier": "pro",
            "features": ["org_dashboard", "trend_reports"],
            "duration_days": 30,
        }
    }


def _session_with_line_items(price_id=TEST_PRICE_ID, session_id="cs_test_a1B2c3D4e5F6g7H8i9J0"):
    return {
        "id": session_id,
        "object": "checkout.session",
        "customer": "cus_TESTfakecustomer1",
        "customer_email": "test-customer@example.com",
        "payment_status": "paid",
        "status": "complete",
        "line_items": {
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
        },
    }


def test_issues_verifiable_license_for_known_price(keypair, price_tier_map):
    private_key, public_key = keypair
    session = _session_with_line_items()

    token = issue_license_for_checkout_session(session, price_tier_map, private_key)
    assert isinstance(token, str) and token

    payload = verify_license(token, public_key)
    assert payload["tier"] == "pro"
    assert payload["features"] == ["org_dashboard", "trend_reports"]
    assert payload["stripe_price_id"] == TEST_PRICE_ID
    assert payload["stripe_checkout_session_id"] == session["id"]

    expires = datetime.fromisoformat(payload["expires"])
    assert expires > datetime.now(timezone.utc)


def test_unknown_price_id_raises(keypair, price_tier_map):
    private_key, _public_key = keypair
    session = _session_with_line_items(price_id="price_TEST_not_configured")

    with pytest.raises(UnknownPriceError):
        issue_license_for_checkout_session(session, price_tier_map, private_key)


def test_missing_line_items_raises(keypair, price_tier_map):
    private_key, _public_key = keypair
    session = {"id": "cs_test_noLineItems", "object": "checkout.session"}

    with pytest.raises(MissingLineItemsError):
        issue_license_for_checkout_session(session, price_tier_map, private_key)


def test_line_items_present_but_empty_raises(keypair, price_tier_map):
    private_key, _public_key = keypair
    session = _session_with_line_items()
    session["line_items"]["data"] = []

    with pytest.raises(MissingLineItemsError):
        issue_license_for_checkout_session(session, price_tier_map, private_key)


def test_default_price_tier_map_is_genuinely_empty():
    # This MUST stay empty until Swetha creates real Products/Prices in
    # her own Stripe dashboard -- see the module-level comment in
    # license_issuer.py for why no placeholder Price IDs are hardcoded.
    assert DEFAULT_PRICE_TIER_MAP == {}
