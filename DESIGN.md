# DESIGN.md

## 1. Name and framing

`coding-engine-search-optimizer` is a deliberate pun on "SEO" (Search
Engine Optimizer) applied to coding agents instead of web pages: instead
of auditing whether a page ranks well, it audits whether a coding agent's
own session "ranks well" against its own stated intentions.

### The actual gap this fills

Existing agent trajectory benchmarks — TRAJECT-Bench, SWE-bench and
similar harnesses — evaluate an agent's behavior against an **external**
reference: a ground-truth patch, a held-out test suite, a task
specification written by someone other than the agent. They answer "did
the agent solve the task correctly, according to us?"

That is a different (and more thoroughly studied) question than the one
this tool asks: **did the agent do what it itself said it was going to
do?** During a long coding session an agent frequently states an
intention mid-conversation — "I'll update `auth.py` to fix the token
refresh bug" — and then, due to context window pressure, plan decay, or
simply moving on to the next sub-problem, may never actually apply that
change, or may apply something different and never acknowledge the
discrepancy. Nothing in the standard trajectory-benchmark toolchain checks
for that kind of *self*-inconsistency, because those benchmarks don't
have (or need) a notion of "what did the agent itself commit to."

This is a narrower and more mechanical check than "was the task done
well." It will flag both genuinely bad drift (the agent silently abandoned
a real fix) and cases that are actually fine (the agent revised its plan
out loud, or referenced a file loosely without meaning it as a firm
commitment). Day 1 does not attempt to distinguish those cases beyond the
`no_file_reference` / `not_found` / `applied` classification described
below — that nuance is future work, not something this tool claims to
solve today.

## 2. Open-core split

**Free forever:** the single-session CLI audit
(`solution_optimizer.cli audit`). Given one transcript and one diff, it
extracts stated solutions, checks adherence, and prints a report. No
license, no network call, no account needed.

**Planned paid (enterprise tier) — NOT built in this repo yet:**
- Org-wide dashboards aggregating adherence across many sessions/repos.
- CI integration (a GitHub Action wrapping the CLI, gating merges on
  adherence thresholds).
- Historical trend reports across many sessions over time.

These are represented today only as named constants
(`ORG_DASHBOARD`, `CI_INTEGRATION`, `TREND_REPORTS` in
`solution_optimizer/license/gate.py`) and a `LicenseGate.require_feature()`
scaffold that would raise `LicenseRequiredError` if code tried to use
them. No dashboard, CI Action, or trend-report code exists in this repo —
see `BUILD-SCHEDULE.md` for when each is planned.

## 3. Day-1 heuristic extractor: known limitations

`solution_optimizer/extract.py` is a plain regex-based extractor, not an
LLM-based one. It looks for sentences containing a small fixed list of
decision-declaring trigger phrases ("I'll", "I will", "Let's", "I'm going
to", "I am going to") and pulls file-path-looking tokens
(`[\w./\-]+\.\w+`) out of that same sentence.

Documented, tested limitations (see the module docstring and
`tests/test_extract.py::test_extract_known_limitation_*` for the concrete
proof cases):

- **False negatives:** any decision phrased without one of the trigger
  words is invisible to this extractor — e.g. "The fix here is to update
  `config.py`" is never picked up. Decisions split across two sentences
  (plan in one, file in the next) also lose the file reference, since
  extraction is scoped per-sentence.
- **False positives:** hedged or rejected options that happen to use a
  trigger phrase ("I could fix `db.py` but I won't") are extracted as if
  committed, because this version has no negation handling.

Day 2 (see `BUILD-SCHEDULE.md`) plans an LLM-based extractor behind an
injected client `Protocol`, with a `Fake` client used in tests — the same
dependency-injection pattern already used in this account's
`weekly-ai-tutor` repo for its LLM-backed grading logic. That keeps the
day-2 extractor's tests fully offline and deterministic, with no live-API
dependency required to run the test suite; a real client would only be
exercised in a separate, explicitly-labeled integration path if/when an
API key is available.

## 4. Licensing mechanism

`solution_optimizer/license/` implements offline, asymmetrically-signed
license tokens using Ed25519 (via the `cryptography` package):

- A license is a JSON payload (tier, feature list, optional expiry) plus
  an Ed25519 signature over that payload's canonical JSON encoding,
  base64-packaged into one opaque token string.
- Verification (`verify_license`) only needs the repo's public key — it
  never calls out to a server. This is the same basic model used by
  commercial offline-licensing tools like Keygen: sign once at issuance
  time, verify anywhere without a network round trip.
- `LicenseGate` reads a token from the `CESO_LICENSE_KEY` environment
  variable (or an explicit string), verifies it against the repo's
  embedded public key, and exposes `.tier`, `.has_feature(name)`, and
  `.require_feature(name)`.
- The repo's real Ed25519 keypair was generated once by
  `scripts/generate_dev_keypair.py`. The public key is embedded directly
  in `gate.py` (public keys are meant to be shared). The private key was
  written to `dev_keys/private_key.pem`, which is listed in `.gitignore`
  and was never committed or pushed — see the README for how to verify
  this yourself.

## 5. No payment integration exists yet

This is explicit and important: **nothing in this repo calls, references,
or embeds credentials for any payment processor.** There is no Stripe
integration, no webhook handler, and no real API key anywhere in this
codebase. The account owner has not yet set up a Stripe account.

The plan (see `BUILD-SCHEDULE.md`, day 6+) is: once a real Stripe account
exists, Stripe's Managed Payments product (a merchant-of-record offering
Stripe now provides) is the intended path, and a future day will add a
webhook handler that calls `solution_optimizer.license.keys.sign_license`
automatically after a successful payment event. That handler does not
exist today. Until then, `scripts/issue_license.py` (day 5, also not
built yet) is meant to be a manual CLI Swetha runs herself after
confirming payment by hand — i.e., today's scaffold only supports manual,
human-triggered license issuance, and even that script is future work,
not part of this day-1 commit.
