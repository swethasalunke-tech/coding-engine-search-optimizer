# BUILD-SCHEDULE.md

Status key: `[done]` = built and tested in this repo today. `[planned]` =
not built yet; described here so scope stays honest and traceable.

## Day 1 — this commit `[done]`

- `solution_optimizer/schema.py`: `Message` / `Transcript` dataclasses with
  real validation.
- `solution_optimizer/extract.py`: deterministic regex-based heuristic
  extractor for stated solutions (no LLM, no live API).
- `solution_optimizer/diff_check.py`: unified-diff parser + adherence
  classification (`applied` / `not_found` / `no_file_reference`).
- `solution_optimizer/report.py`: `AdherenceReport` aggregation + markdown
  rendering.
- `solution_optimizer/cli.py`: free, runnable `audit` command, no license
  required.
- `solution_optimizer/license/keys.py` + `gate.py`: offline Ed25519
  license sign/verify and a `LicenseGate` scaffold for the (not-yet-built)
  enterprise features. No payment integration.
- `scripts/generate_dev_keypair.py`: run once to produce this repo's real
  embedded public key; private key kept local and git-ignored.
- Full test suite (`tests/`), all passing.

## Day 2 — LLM-based extractor v2 `[planned]`

- Add a `SolutionExtractorClient` `Protocol` (or similarly named
  interface) that `extract.py` (or a new `extract_llm.py`) can call
  through, so the extraction logic is decoupled from any specific LLM
  vendor/SDK.
- Provide a `FakeSolutionExtractorClient` for tests, following the same
  dependency-injection pattern already used in this account's
  `weekly-ai-tutor` repo for grading — tests stay deterministic and
  offline by default.
- If a real API key is available in the dev environment when this day is
  built, a *separate*, clearly-labeled integration test path may exercise
  a real client — but it will be honestly marked as requiring a live key,
  skipped by default, and never silently faked. If no key is available
  when this day is built, that limitation will be documented plainly
  rather than papered over with invented "example" output.
- Goal: catch decisions phrased without the day-1 trigger-phrase list
  (see DESIGN.md's documented false-negative cases).

## Day 3 — CI integration `[planned]`

- A GitHub Action (composite action or Docker action) that wraps
  `python -m solution_optimizer.cli audit` for use in pull-request checks.
- This is one of the three enterprise features named in
  `solution_optimizer/license/gate.py` (`CI_INTEGRATION`) — the Action
  itself will call `LicenseGate.require_feature(CI_INTEGRATION)` before
  running anything beyond the free single-session audit path.
- Not started; no workflow YAML exists in this repo yet.

## Day 4 — trend reports `[planned]`

- Aggregate multiple `AdherenceReport` objects (one per session) into a
  trend view: adherence rate over time, per-repo or per-agent-config
  breakdowns.
- This is the first genuinely enterprise-gated feature to actually get
  implementation code (not just a named constant) — every entry point
  will call `LicenseGate.require_feature(TREND_REPORTS)` before producing
  output.
- Not started.

## Day 5 — manual license issuance script `[planned]`

- `scripts/issue_license.py`: a CLI Swetha runs herself, by hand, after
  she has manually confirmed a customer's payment (bank transfer, invoice,
  whatever channel exists before Stripe is wired up). It will call
  `solution_optimizer.license.keys.sign_license` with the appropriate
  tier/features/expiry and print (or write) the resulting token for her
  to send the customer.
- Explicitly manual and human-triggered — no automatic issuance at this
  stage.
- Not started.

## Day 6 — Stripe webhook handler `[done]`

- `solution_optimizer/billing/stripe_webhook.py`: `verify_stripe_signature`
  wraps Stripe's own documented verification helper
  (`stripe.Webhook.construct_event`), and `create_app(webhook_secret,
  price_tier_map, private_key)` builds a real Flask app with one route,
  `POST /webhooks/stripe`. Valid `checkout.session.completed` events issue
  a license token; unrecognized event types get a 200 ("ignored event
  type" — Stripe expects 2xx for events an endpoint doesn't act on, or it
  retries); invalid/tampered signatures get a 400; a recognized event with
  an unrecognized Price ID or missing `line_items` gets a 422 with a clear
  error message (never a silently-issued free license).
- `solution_optimizer/billing/license_issuer.py`:
  `issue_license_for_checkout_session` pulls the Stripe Price ID out of
  the Checkout Session's (expanded) `line_items`, looks up the tier in a
  `price_tier_map`, and calls the existing day-1
  `solution_optimizer.license.keys.sign_license` — reused, not
  reimplemented. Raises `MissingLineItemsError` if `line_items` wasn't
  expanded rather than guessing a tier, and `UnknownPriceError` if the
  Price ID has no configured mapping.
- Full local test coverage (`tests/test_stripe_webhook.py`,
  `tests/test_license_issuer.py`) using synthetic Stripe payloads: a real
  `checkout.session.completed` event JSON shaped to match Stripe's
  publicly documented event/object formats, signed with the official
  `stripe` SDK's own `stripe.WebhookSignature.generate_signature_header`
  helper (its docstring: "Useful for signing payloads in unit tests")
  against a self-chosen test webhook secret
  (`whsec_test_placeholder_do_not_use_live`) that has never been
  registered with Stripe. One test round-trips a full webhook POST
  through both `billing` (issuance) and `license` (verification) modules.
  All 68 day-1 tests still pass unchanged, plus 12 new tests — 80 total.
- **What this is NOT, explicitly:**
  - **No real Stripe Products/Prices exist yet.**
    `license_issuer.DEFAULT_PRICE_TIER_MAP` is genuinely `{}` — it has not
    been populated with real Stripe Price IDs, because the account owner
    hasn't created any real Products/Prices in her Stripe dashboard yet.
    No fake-but-plausible-looking Price IDs are hardcoded anywhere in this
    repo.
  - **No deployment or hosting.** `create_app()` only runs locally (e.g.
    via `flask run` or a manual `app.run()`); there is no server, no
    public URL, and no registered webhook endpoint in Stripe pointing at
    anything yet.
  - **The issued token is returned in the HTTP response body.** That's a
    day-6 local-testing simplification, documented as such in
    `stripe_webhook.py`'s docstring — not a production delivery
    mechanism. A real deployment must store/email the token instead of
    echoing it back in the webhook response.
  - **No live Stripe event has ever hit this code.** Every payload used
    in development and testing is a synthetic JSON object built by hand
    to match Stripe's publicly documented shapes, never data Stripe
    actually sent. See the README's "Testing the Stripe webhook locally"
    section for the (manual, not-yet-run) steps to change that using the
    Stripe CLI in test mode.
