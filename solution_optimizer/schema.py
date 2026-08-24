"""Core data model for a coding-agent transcript.

A ``Transcript`` is just an ordered list of ``Message`` objects exchanged
between a "user" (the human, or a tool/system acting on the human's behalf)
and an "assistant" (the coding agent). Validation here is deliberately
strict and synchronous — it runs at construction time so that anything
downstream (extraction, diff-checking, reporting) can assume it is working
with well-formed data and never has to re-check basic invariants.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VALID_ROLES = ("user", "assistant")


class TranscriptValidationError(ValueError):
    """Raised when a Transcript or Message fails validation."""


@dataclass(frozen=True)
class Message:
    """A single turn in a transcript.

    Attributes:
        role: Either "user" or "assistant".
        content: The raw text content of the message. Must be non-empty
            (after stripping whitespace).
        index: The zero-based position of this message within its parent
            Transcript's message list.
    """

    role: str
    content: str
    index: int

    def __post_init__(self) -> None:
        if self.role not in VALID_ROLES:
            raise TranscriptValidationError(
                f"Message.role must be one of {VALID_ROLES!r}, got {self.role!r}"
            )
        if not isinstance(self.content, str) or not self.content.strip():
            raise TranscriptValidationError(
                f"Message.content must be a non-empty string (message index {self.index})"
            )
        if not isinstance(self.index, int) or self.index < 0:
            raise TranscriptValidationError(
                f"Message.index must be a non-negative int, got {self.index!r}"
            )


@dataclass(frozen=True)
class Transcript:
    """An ordered, validated sequence of messages for one agent session.

    Attributes:
        messages: The ordered list of Message objects. Must be non-empty
            and have strictly sequential indices starting at 0 (0, 1, 2, ...),
            matching each Message's own `.index` field and its position in
            the list.
        session_id: A non-empty identifier for the session this transcript
            was captured from.
    """

    messages: list[Message] = field(default_factory=list)
    session_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise TranscriptValidationError("Transcript.session_id must be a non-empty string")
        if not self.messages:
            raise TranscriptValidationError("Transcript.messages must be non-empty")
        for expected_index, msg in enumerate(self.messages):
            if not isinstance(msg, Message):
                raise TranscriptValidationError(
                    f"Transcript.messages[{expected_index}] is not a Message instance"
                )
            if msg.index != expected_index:
                raise TranscriptValidationError(
                    "Transcript.messages must have sequential indices starting at 0: "
                    f"expected index {expected_index} at position {expected_index}, "
                    f"found index {msg.index}"
                )

    def assistant_messages(self) -> list[Message]:
        """Return only the messages authored by the assistant, in order."""
        return [m for m in self.messages if m.role == "assistant"]

    @staticmethod
    def from_dict(data: dict) -> "Transcript":
        """Build a Transcript from a plain dict (e.g. loaded from JSON).

        Expected shape::

            {
                "session_id": "abc123",
                "messages": [
                    {"role": "user", "content": "...", "index": 0},
                    {"role": "assistant", "content": "...", "index": 1}
                ]
            }
        """
        if not isinstance(data, dict):
            raise TranscriptValidationError("Transcript.from_dict expects a dict")
        raw_messages = data.get("messages")
        if not isinstance(raw_messages, list):
            raise TranscriptValidationError("Transcript.from_dict: 'messages' must be a list")
        messages = []
        for raw in raw_messages:
            if not isinstance(raw, dict):
                raise TranscriptValidationError("Each message must be a dict")
            messages.append(
                Message(
                    role=raw.get("role"),
                    content=raw.get("content"),
                    index=raw.get("index"),
                )
            )
        return Transcript(messages=messages, session_id=data.get("session_id", ""))
