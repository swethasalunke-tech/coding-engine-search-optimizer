"""Offline Ed25519-signed license scaffold for the future paid enterprise
tier (org dashboards, CI integration, trend reports).

Nothing in this package talks to a payment processor. No live API is
called from anywhere here. See DESIGN.md for the full explanation of why
(the account owner has not set up Stripe yet) and BUILD-SCHEDULE.md for
when a webhook-driven auto-issuance flow is planned.
"""
