"""solution_optimizer: audits whether a coding agent followed through on the
solutions it proposed mid-session.

See DESIGN.md at the repo root for the full rationale. In short: existing
agent trajectory benchmarks (e.g. TRAJECT-Bench, SWE-bench style harnesses)
check an agent's final behavior against an *external* reference plan or
test suite. This package checks something different and narrower: did the
agent apply the fix / plan *it itself stated* mid-conversation, or did it
drift, contradict itself, or silently abandon its own earlier decision?
"""

__version__ = "0.1.0"
