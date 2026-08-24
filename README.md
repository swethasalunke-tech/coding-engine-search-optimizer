# coding-engine-search-optimizer

A pun on "SEO" (Search Engine Optimizer) — this audits coding *agents*,
not web pages. Given one recorded coding-agent session (a transcript) and
the diff it produced, it checks whether the agent actually followed
through on the solutions it said, mid-conversation, that it would apply —
as opposed to drifting, contradicting itself, or silently abandoning its
own earlier stated plan.

This is a different question from what trajectory benchmarks like
TRAJECT-Bench or SWE-bench answer (they check an agent's output against an
*external* reference plan). This tool checks an agent's *self*-consistency
against its own stated plan. See `DESIGN.md` for the full rationale.

## What's free forever

The entire single-session CLI audit:

```
python -m solution_optimizer.cli audit --transcript path.json --diff path.diff
```

This runs the full pipeline — heuristic extraction of stated solutions,
unified-diff parsing, adherence classification, markdown report — with no
license, no account, and no network call required. It always will be
free.

## What's planned as a paid tier (NOT built yet)

- Org-wide dashboards aggregating adherence across many sessions.
- CI integration (a GitHub Action wrapping the CLI).
- Historical trend reports across many sessions over time.

None of that exists in this repo today. What *does* exist today is only
the licensing **scaffold** that those future features will be gated
behind (`solution_optimizer/license/`) — three named feature constants
(`ORG_DASHBOARD`, `CI_INTEGRATION`, `TREND_REPORTS`) and a `LicenseGate`
class with `has_feature()` / `require_feature()`. There is no dashboard
code, no CI Action, and no trend-report code anywhere in this repo. See
`BUILD-SCHEDULE.md` for the honest day-by-day plan.

**No payment processor integration exists yet.** No Stripe code, no
webhook handler, no real or placeholder payment API keys anywhere in this
codebase. The account owner plans to set up her own Stripe account later
(Stripe's Managed Payments product) — see `DESIGN.md` section 5 and
`BUILD-SCHEDULE.md` day 6+ for what that will look like once it exists.
Until then, license tokens can only be issued manually, by hand, by
calling `solution_optimizer.license.keys.sign_license` directly (there
isn't even a manual issuance CLI in this repo yet — that's day 5).

## Installing

```
pip install -r requirements.txt
```

Requires `cryptography` (for the Ed25519 license signing/verification)
and `pytest` (for the test suite).

## Running the tests

```
python3 -m pytest tests/ -v
```

All 68 tests are real and pass locally, including a real subprocess
invocation of the CLI (`tests/test_cli.py`) against fixture data in
`tests/fixtures/`.

## Running the CLI

```
python -m solution_optimizer.cli audit \
  --transcript tests/fixtures/transcript_basic.json \
  --diff tests/fixtures/diff_basic.diff
```

Example real output against that fixture pair:

```
# Solution Adherence Report

3 stated solution(s): 2 applied, 1 not found, 0 no file reference -- adherence rate: 67%

| # | Verdict | Matched File | Message # | Stated Text |
|---|---------|--------------|-----------|-------------|
| 1 | applied | auth.py | 1 | I'll update auth.py to fix the token refresh bug. |
| 2 | not_found | - | 1 | Let's also add a test in test_auth.py to cover this case. |
| 3 | applied | config.py | 3 | I'm going to update config.py to bump the timeout value as well. |
```

Bring your own transcript JSON (see `tests/fixtures/transcript_basic.json`
for the expected shape: `{"session_id": ..., "messages": [{"role":
"user"|"assistant", "content": ..., "index": ...}, ...]}`) and a standard
unified diff (`git diff` output works directly).

## The day-1 extractor is intentionally simple

`solution_optimizer/extract.py` uses plain regex matching on trigger
phrases ("I'll", "I will", "Let's", "I'm going to", "I am going to") plus
file-path-token extraction from the same sentence. It is not LLM-based.
Its known false-negative and false-positive cases are documented in the
module docstring, in `DESIGN.md`, and proven with dedicated test cases in
`tests/test_extract.py`. A day-2 LLM-based extractor is planned (see
`BUILD-SCHEDULE.md`) behind an injected client interface with a fake for
tests, so no live API key will ever be required just to run this repo's
test suite.

## How the license gate works, and how to test it locally

License tokens are offline, Ed25519-signed JSON payloads — no server, no
phone-home, same basic approach as tools like Keygen. `LicenseGate`:

- reads a token from the `CESO_LICENSE_KEY` environment variable (or an
  explicit string passed to its constructor),
- verifies it against this repo's embedded public key
  (`solution_optimizer/license/gate.py`'s `_PUBLIC_KEY_HEX`),
- exposes `.tier` (`"free"` if no/invalid/expired token), `.has_feature(name)`,
  and `.require_feature(name)` (raises `LicenseRequiredError` with a clear
  upgrade message when the current license doesn't grant the requested
  feature).

To issue yourself a test license locally and see a gated feature respond:

```python
import json
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from solution_optimizer.license.keys import sign_license
from solution_optimizer.license.gate import LicenseGate, ORG_DASHBOARD

# Load the private key generated by scripts/generate_dev_keypair.py.
# NEVER commit dev_keys/ -- it's git-ignored on purpose.
private_key = load_pem_private_key(
    open("dev_keys/private_key.pem", "rb").read(), password=None
)

payload = {
    "tier": "enterprise",
    "features": [ORG_DASHBOARD],
    "expires": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
}
token = sign_license(payload, private_key)

import os
os.environ["CESO_LICENSE_KEY"] = token
gate = LicenseGate()
print(gate.tier)                      # "enterprise"
print(gate.has_feature(ORG_DASHBOARD))  # True
```

Note that `dev_keys/private_key.pem` only exists on machines where
`scripts/generate_dev_keypair.py` has been run (or where it was generated
for this repo's real key) — it is git-ignored and never pushed. The
license *tests* (`tests/test_license.py`, `tests/test_gate.py`) don't
depend on it at all: they generate their own throwaway keypairs so the
test suite never touches the repo's real private key.

## Repository layout

```
solution_optimizer/
  schema.py          Message / Transcript dataclasses + validation
  extract.py          heuristic stated-solution extractor (day 1)
  diff_check.py        unified diff parser + adherence classification
  report.py            AdherenceReport aggregation + markdown rendering
  cli.py                free `audit` command
  license/
    keys.py             Ed25519 sign/verify primitives
    gate.py              LicenseGate + feature constants (scaffold only)
scripts/
  generate_dev_keypair.py   one-time keypair generation for this repo
tests/                  full pytest suite + fixtures
DESIGN.md               full design rationale
BUILD-SCHEDULE.md       honest day-by-day build plan
```
