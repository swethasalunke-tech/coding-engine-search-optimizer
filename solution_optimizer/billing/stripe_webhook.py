"""Stripe webhook signature verification + a Flask route that turns a
`checkout.session.completed` event into an issued license token.

NO REAL STRIPE API KEY was used to build or test anything in this module,
and none is required by anything in it. Signature verification only needs
a webhook *signing secret* (a `whsec_...` string, generated per-endpoint
by the Stripe CLI or dashboard) -- a materially different, lower-privilege
credential than an API key. This module was built and tested entirely
against synthetic payloads signed with a self-chosen placeholder secret;
see `tests/test_stripe_webhook.py` for exactly how, and BUILD-SCHEDULE.md
for what has (and has not) been verified against real Stripe traffic.
"""

from __future__ import annotations

from typing import Any

import stripe
from flask import Flask, jsonify, request

from solution_optimizer.billing.license_issuer import (
    MissingLineItemsError,
    PriceTierMap,
    UnknownPriceError,
    issue_license_for_checkout_session,
)


class InvalidWebhookSignatureError(Exception):
    """Raised when a webhook payload's Stripe-Signature header does not
    verify against the configured webhook secret. Wraps
    stripe.error.SignatureVerificationError so callers of this module
    don't need to import the stripe package directly to catch it."""


def verify_stripe_signature(payload: bytes, sig_header: str, webhook_secret: str) -> dict:
    """Verify a raw webhook request body against its Stripe-Signature
    header using Stripe's own documented verification helper
    (`stripe.Webhook.construct_event`), and return the parsed event as a
    plain dict on success.

    This requires only the endpoint's webhook signing secret -- not a
    Stripe API key. No API key is used, read, or required anywhere in
    this function.

    Raises:
        InvalidWebhookSignatureError: the signature does not verify
            (wrong secret, tampered payload, malformed header, or expired
            timestamp beyond stripe's default tolerance).
    """
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError as exc:
        raise InvalidWebhookSignatureError(str(exc)) from exc
    return event.to_dict()


def create_app(webhook_secret: str, price_tier_map: PriceTierMap, private_key: Any) -> Flask:
    """Build a Flask app exposing a single route, POST /webhooks/stripe.

    Behavior:
    - Reads the raw request body + Stripe-Signature header and verifies
      them with verify_stripe_signature(). Invalid/tampered signatures
      get a 400 response.
    - If the verified event's type is "checkout.session.completed", looks
      up the purchased Price ID via
      solution_optimizer.billing.license_issuer and issues a signed
      license token. Unknown Price IDs or missing line_items get a 422
      response with a clear error message (never a silently-issued free
      license).
    - Any other event type gets a 200 response with an "ignored event
      type" body -- Stripe expects a 2xx response for event types an
      endpoint doesn't act on, and will retry (with backoff, eventually
      disabling the endpoint) on anything else.

    DAY-6 SIMPLIFICATION, EXPLICITLY NOT PRODUCTION-READY: on success,
    this route returns the issued license token directly in the HTTP
    response body (as JSON). That is only acceptable for local testing.
    In a real deployment, a webhook response is not an authenticated
    channel back to the paying customer -- anyone who could see the HTTP
    response (proxies, logs, Stripe's own webhook delivery UI) would see
    the license token too. A production version of this route must
    instead store the issued token server-side (e.g. keyed by
    stripe_checkout_session_id) and deliver it to the customer through an
    authenticated channel (email to the address on the Checkout Session,
    a logged-in account page, etc.), returning only an acknowledgement
    (e.g. {"status": "license issued"}) in the webhook response itself.
    That storage/delivery step is not built yet -- see BUILD-SCHEDULE.md.
    """
    app = Flask(__name__)

    @app.route("/webhooks/stripe", methods=["POST"])
    def stripe_webhook():
        payload = request.get_data()
        sig_header = request.headers.get("Stripe-Signature", "")

        try:
            event = verify_stripe_signature(payload, sig_header, webhook_secret)
        except InvalidWebhookSignatureError as exc:
            return jsonify({"error": f"invalid webhook signature: {exc}"}), 400

        event_type = event.get("type")
        if event_type != "checkout.session.completed":
            return (
                jsonify({"status": "ignored event type", "type": event_type}),
                200,
            )

        session = (event.get("data") or {}).get("object") or {}

        try:
            token = issue_license_for_checkout_session(session, price_tier_map, private_key)
        except MissingLineItemsError as exc:
            return jsonify({"error": str(exc)}), 422
        except UnknownPriceError as exc:
            return jsonify({"error": str(exc)}), 422

        # See the DAY-6 SIMPLIFICATION note in this function's docstring:
        # returning the token inline here is a local-testing shortcut,
        # not a production delivery mechanism.
        return (
            jsonify(
                {
                    "status": "license issued",
                    "license_token": token,
                    "stripe_checkout_session_id": session.get("id"),
                }
            ),
            200,
        )

    return app
