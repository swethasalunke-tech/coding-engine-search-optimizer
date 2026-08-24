import pytest

from solution_optimizer.schema import Message, Transcript, TranscriptValidationError


def test_message_valid():
    m = Message(role="user", content="hello", index=0)
    assert m.role == "user"
    assert m.content == "hello"
    assert m.index == 0


@pytest.mark.parametrize("role", ["system", "tool", "", "USER", "Assistant"])
def test_message_invalid_role(role):
    with pytest.raises(TranscriptValidationError):
        Message(role=role, content="hello", index=0)


@pytest.mark.parametrize("content", ["", "   ", "\n\t"])
def test_message_empty_content_rejected(content):
    with pytest.raises(TranscriptValidationError):
        Message(role="user", content=content, index=0)


def test_message_negative_index_rejected():
    with pytest.raises(TranscriptValidationError):
        Message(role="user", content="hi", index=-1)


def test_transcript_valid():
    t = Transcript(
        messages=[
            Message(role="user", content="hi", index=0),
            Message(role="assistant", content="I'll help.", index=1),
        ],
        session_id="s1",
    )
    assert len(t.messages) == 2
    assert t.session_id == "s1"


def test_transcript_empty_messages_rejected():
    with pytest.raises(TranscriptValidationError):
        Transcript(messages=[], session_id="s1")


def test_transcript_empty_session_id_rejected():
    with pytest.raises(TranscriptValidationError):
        Transcript(
            messages=[Message(role="user", content="hi", index=0)],
            session_id="",
        )


def test_transcript_non_sequential_indices_rejected():
    with pytest.raises(TranscriptValidationError):
        Transcript(
            messages=[
                Message(role="user", content="hi", index=0),
                Message(role="assistant", content="ok", index=2),
            ],
            session_id="s1",
        )


def test_transcript_indices_must_start_at_zero():
    with pytest.raises(TranscriptValidationError):
        Transcript(
            messages=[Message(role="user", content="hi", index=1)],
            session_id="s1",
        )


def test_transcript_assistant_messages_filter():
    t = Transcript(
        messages=[
            Message(role="user", content="hi", index=0),
            Message(role="assistant", content="I'll help.", index=1),
            Message(role="user", content="thanks", index=2),
            Message(role="assistant", content="Done.", index=3),
        ],
        session_id="s1",
    )
    assistant_msgs = t.assistant_messages()
    assert [m.index for m in assistant_msgs] == [1, 3]


def test_transcript_from_dict():
    data = {
        "session_id": "s2",
        "messages": [
            {"role": "user", "content": "hi", "index": 0},
            {"role": "assistant", "content": "I'll fix it.", "index": 1},
        ],
    }
    t = Transcript.from_dict(data)
    assert t.session_id == "s2"
    assert len(t.messages) == 2


def test_transcript_from_dict_bad_messages_type():
    with pytest.raises(TranscriptValidationError):
        Transcript.from_dict({"session_id": "s1", "messages": "not a list"})


def test_transcript_from_dict_not_a_dict():
    with pytest.raises(TranscriptValidationError):
        Transcript.from_dict(["not", "a", "dict"])
