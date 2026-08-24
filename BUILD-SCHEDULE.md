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

## Day 6+ — Stripe webhook handler `[planned, blocked on a real Stripe account]`

- Only to be built once the account owner has actually created a Stripe
  account and has real (non-test-placeholder) API keys. Stripe's Managed
  Payments product (a merchant-of-record offering) is the intended
  integration point, since it removes the need to separately register as
  a payment facilitator.
- Will add a webhook endpoint/handler that listens for a successful
  payment event and calls the same `sign_license` function
  `scripts/issue_license.py` uses, automating what day 5 does by hand.
- Explicitly **not** part of this repo until that account exists — there
  is no placeholder Stripe code, no dummy webhook route, and no reference
  to real or fake Stripe API keys anywhere in the day-1 commit.
