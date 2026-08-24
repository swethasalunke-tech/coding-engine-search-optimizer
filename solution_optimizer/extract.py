"""Day-1 heuristic extractor for "stated solutions" in assistant messages.

WHAT THIS IS: a deliberately simple, deterministic, regex-based extractor.
It looks for sentences in assistant messages that use decision-declaring
phrasing ("I'll ...", "I will ...", "Let's ...", "I'm going to ...", "I am
going to ...") and pulls out any file-path-looking tokens from that same
sentence.

WHAT THIS IS NOT (yet): this is NOT an LLM-based extractor. There is no
live API call anywhere in this module. Day 2 (see BUILD-SCHEDULE.md) will
add an LLM-based extractor behind an injected client Protocol, with a Fake
client for tests, so that semantically-stated solutions that don't match
these surface patterns can also be caught.

KNOWN LIMITATIONS (v1, honest, by design):
  False negatives:
    - Any decision phrased without one of the trigger phrases, e.g.
      "The fix here is to update config.py" or "Switching to a retry loop
      in worker.py" will NOT be detected — no regex trigger matches.
    - Decisions split across multiple sentences (stating the plan in one
      sentence, the file in the next) will NOT have the file path captured,
      since extraction is scoped to a single sentence.
    - Decisions stated with contractions or informal phrasing outside the
      known trigger list (e.g. "Gonna refactor auth.py") are missed.
  False positives:
    - Hypothetical or rejected options phrased with the same trigger
      words ("I could fix db.py but I won't" / "I'll avoid touching
      cli.py") are still extracted as if they were commitments — this
      extractor does not understand negation or hedging.
    - Trigger phrases used outside of a genuine decision context (e.g.
      quoting the user: "You said 'I'll handle it'") are still matched.

This module is intentionally conservative in scope so its behavior is easy
to reason about and test. Sophistication is a day-2 problem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from solution_optimizer.schema import Transcript

# Sentence splitter: split on '.', '!', '?' followed by whitespace or end of
# string. This is a simple heuristic split, not a full NLP sentence
# tokenizer — it will mis-split on abbreviations like "e.g." or version
# strings like "v1.2.3", which is a known limitation shared with the rest
# of this module's simplicity trade-off.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Decision-declaring trigger phrases, case-insensitive, matched anywhere in
# a sentence.
_TRIGGER_RE = re.compile(
    r"\b(i'll|i will|let's|lets|i'm going to|i am going to)\b",
    re.IGNORECASE,
)

# File-path-looking token: word characters, dots, slashes, hyphens, with at
# least one '.' followed by a word-character extension. Deliberately loose.
_PATH_RE = re.compile(r"\b[\w./\-]+\.\w+\b")

# Trailing punctuation that can get swept up by the path regex when a path
# ends a sentence (e.g. "update config.py." -> "config.py.").
_TRAILING_PUNCT_RE = re.compile(r"[.,;:!?]+$")


@dataclass(frozen=True)
class StatedSolution:
    """A single decision-declaring sentence extracted from an assistant
    message, along with any file paths mentioned in that same sentence.

    Attributes:
        text: The full sentence (trimmed) that triggered extraction.
        message_index: The index of the Message this sentence came from.
        referenced_paths: File-path-looking tokens found in the same
            sentence. May be empty — that is expected and meaningful (see
            diff_check.py's "no_file_reference" classification), not an
            extraction failure.
    """

    text: str
    message_index: int
    referenced_paths: list[str] = field(default_factory=list)


def _split_sentences(content: str) -> list[str]:
    # Normalize newlines to spaces so a trigger phrase and its file
    # reference on adjacent lines within the "same sentence" (no terminal
    # punctuation) are still treated as one unit.
    normalized = " ".join(content.split())
    sentences = _SENTENCE_SPLIT_RE.split(normalized)
    return [s.strip() for s in sentences if s.strip()]


def _extract_paths(sentence: str) -> list[str]:
    raw_matches = _PATH_RE.findall(sentence)
    cleaned = []
    for m in raw_matches:
        m = _TRAILING_PUNCT_RE.sub("", m)
        if m and m not in cleaned:
            cleaned.append(m)
    return cleaned


def extract_stated_solutions(transcript: Transcript) -> list[StatedSolution]:
    """Extract StatedSolution entries from every assistant message in the
    transcript, in message order.

    A sentence becomes a StatedSolution if it contains one of the trigger
    phrases in _TRIGGER_RE. `referenced_paths` will be an empty list when
    no file-path-looking token is present in that sentence (this is a
    common, expected outcome — see module docstring).
    """
    results: list[StatedSolution] = []
    for msg in transcript.messages:
        if msg.role != "assistant":
            continue
        for sentence in _split_sentences(msg.content):
            if _TRIGGER_RE.search(sentence):
                results.append(
                    StatedSolution(
                        text=sentence,
                        message_index=msg.index,
                        referenced_paths=_extract_paths(sentence),
                    )
                )
    return results
