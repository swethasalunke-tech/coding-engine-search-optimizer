"""Turns a successful Stripe payment into an issued license token.

This package listens for Stripe's `checkout.session.completed` webhook
event, verifies its authenticity, looks up which license tier/features the
purchased Stripe Price ID corresponds to, and calls the existing (day-1)
`solution_optimizer.license.keys.sign_license` to produce a signed license
token -- automating what `scripts/issue_license.py` (day 5, manual) does
by hand.

IMPORTANT, for the no-fabrication record: no real Stripe API key was used
to build or test anything in this package, and none is required by any
function in it. Everything here was built and verified using only:

- Stripe's publicly documented webhook signature algorithm (HMAC-SHA256
  over "{timestamp}.{raw_request_body}"), exercised through the official
  `stripe` Python SDK's own `stripe.Webhook.construct_event` (verification)
  and `stripe.WebhookSignature.generate_signature_header` (the SDK's own
  helper, whose docstring says "Useful for signing payloads in unit
  tests") -- both of which operate only on a locally-chosen webhook
  *signing secret* string, not an API key.
- Stripe's publicly documented `checkout.session.completed` event and
  Checkout Session object shapes (docs.stripe.com/api), used to build
  synthetic test payloads in `tests/test_stripe_webhook.py` and
  `tests/test_license_issuer.py`.

No live Stripe event has ever hit this code. `DEFAULT_PRICE_TIER_MAP` in
`license_issuer.py` is genuinely empty -- it has not been populated with
real Stripe Price IDs, because none exist yet (the account owner has not
created any Products/Prices in her Stripe dashboard). See
BUILD-SCHEDULE.md for exactly what is and is not done as of day 6.
"""
