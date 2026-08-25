"""Turns a Stripe `checkout.session.completed` Checkout Session into a
signed license token.

This module has no network dependency and makes no Stripe API call
itself -- it operates purely on a `session` dict already handed to it
(typically the `data.object` of a verified webhook event; see
`solution_optimizer.billing.stripe_webhook`). All signing is delegated to
the existing day-1 `solution_optimizer.license.keys.sign_license` -- this
module does not reimplement signing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from solution_optimizer.license.keys import sign_license

# Maps a Stripe Price ID string (e.g. "price_1AbCDeFgHiJkLmN...") to the
# license tier/features/duration that purchasing that Price should grant.
PriceTierMap = dict[str, dict]


class MissingLineItemsError(Exception):
    """Raised when a checkout.session.completed session dict has no usable
    line_items.

    Stripe's *default* (un-expanded) webhook payload for
    checkout.session.completed only includes the Checkout Session's id,
    customer info, amounts, etc. -- it does NOT include line_items unless
    the session was created with `expand=["line_items"]`, or the caller
    separately calls `stripe.checkout.Session.retrieve(session["id"],
    expand=["line_items"])` after receiving the webhook. (See
    https://docs.stripe.com/api/checkout/sessions/object and
    https://docs.stripe.com/expand for Stripe's documented expand
    behavior.) This error exists so a missing expansion fails loudly
    instead of this module silently guessing a tier.
    """


class UnknownPriceError(Exception):
    """Raised when a checkout session's Stripe Price ID is not a key in
    the supplied price_tier_map -- i.e. a real payment came in for a Price
    that has no configured tier/feature mapping yet."""


# Empty by default, intentionally. This MUST be populated with Swetha's
# real Stripe Price IDs, taken from the actual Products/Prices she creates
# in her own Stripe dashboard, before any license can be auto-issued from
# a real payment. As of day 6, no such Products/Prices exist yet, so
# there is nothing real to put here.
#
# No fake-but-plausible-looking Price IDs (real ones look like
# "price_1AbCDeFgHiJkLmNoPqRsTuV") are hardcoded below -- inventing IDs
# that look real and shipping them in this map would itself be exactly
# the kind of fabrication this account's no-fabrication rule prohibits.
#
# Documented example shape only (NOT a real Price ID, for illustration):
#
#   DEFAULT_PRICE_TIER_MAP = {
#       "price_1AbCDeFgHiJkLmNoPqRsTuV": {
#           "tier": "pro",
#           "features": ["org_dashboard"],
#           "duration_days": 365,
#       },
#   }
DEFAULT_PRICE_TIER_MAP: PriceTierMap = {}


def issue_license_for_checkout_session(
    session: dict, price_tier_map: PriceTierMap, private_key: Any
) -> str:
    """Issue a signed license token for a completed Stripe Checkout
    Session.

    `session` is the Checkout Session dict as found in a verified
    `checkout.session.completed` event's `data.object` (see
    `solution_optimizer.billing.stripe_webhook.verify_stripe_signature`).

    Raises:
        MissingLineItemsError: `session` has no `line_items.data` -- the
            caller needs to have created the Checkout Session with
            `expand=["line_items"]`, or fetched it separately with that
            expansion, before this function can determine what was
            purchased.
        UnknownPriceError: the purchased Price ID isn't a key in
            `price_tier_map`.

    Returns the signed license token string (see
    `solution_optimizer.license.keys.sign_license`).
    """
    line_items = session.get("line_items")
    if not line_items or not line_items.get("data"):
        raise MissingLineItemsError(
            "checkout.session.completed session has no line_items -- "
            "create the Checkout Session with expand=[\"line_items\"], or "
            "fetch it separately via "
            "stripe.checkout.Session.retrieve(session['id'], "
            "expand=[\"line_items\"]), before calling "
            "issue_license_for_checkout_session()."
        )

    first_item = line_items["data"][0]
    price = first_item.get("price") or {}
    price_id = price.get("id")

    if not price_id:
        raise MissingLineItemsError(
            "checkout.session.completed session's first line_item has no "
            "price.id -- the line_items expansion may be incomplete."
        )

    if price_id not in price_tier_map:
        raise UnknownPriceError(
            f"no tier configured for Stripe Price ID {price_id!r}. Add it "
            "to the price_tier_map passed to create_app() / "
            "issue_license_for_checkout_session()."
        )

    tier_config = price_tier_map[price_id]
    duration_days = tier_config["duration_days"]
    expires = (datetime.now(timezone.utc) + timedelta(days=duration_days)).isoformat()

    payload = {
        "tier": tier_config["tier"],
        "features": list(tier_config.get("features", [])),
        "expires": expires,
        "stripe_checkout_session_id": session.get("id"),
        "stripe_price_id": price_id,
    }

    return sign_license(payload, private_key)
