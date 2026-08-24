import json
from pathlib import Path

from solution_optimizer.extract import extract_stated_solutions
from solution_optimizer.schema import Message, Transcript

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> Transcript:
    data = json.loads((FIXTURES_DIR / name).read_text())
    return Transcript.from_dict(data)


def test_extract_basic_fixture_finds_three_solutions():
    transcript = _load_fixture("transcript_basic.json")
    solutions = extract_stated_solutions(transcript)

    assert len(solutions) == 3

    assert "auth.py" in solutions[0].referenced_paths
    assert solutions[0].message_index == 1

    assert "test_auth.py" in solutions[1].referenced_paths
    assert solutions[1].message_index == 1

    assert "config.py" in solutions[2].referenced_paths
    assert solutions[2].message_index == 3


def test_extract_ignores_user_messages():
    transcript = Transcript(
        messages=[
            Message(role="user", content="I'll rewrite everything in main.py.", index=0),
            Message(role="assistant", content="Sure, sounds fine.", index=1),
        ],
        session_id="s1",
    )
    solutions = extract_stated_solutions(transcript)
    assert solutions == []


def test_extract_known_limitation_no_file_reference():
    """Documents a known false-negative-adjacent limitation: a stated
    decision with no file-path-looking token in the same sentence yields
    an empty referenced_paths list, not a missed extraction. This is the
    expected, honestly-documented behavior (see extract.py docstring)."""
    transcript = _load_fixture("transcript_no_file_ref.json")
    solutions = extract_stated_solutions(transcript)

    assert len(solutions) == 1
    assert solutions[0].referenced_paths == []
    assert solutions[0].message_index == 1


def test_extract_known_limitation_no_trigger_phrase_is_missed():
    """Documents the other known limitation: decisions phrased without one
    of the trigger phrases are not detected at all, even with an obvious
    file reference."""
    transcript = Transcript(
        messages=[
            Message(role="user", content="How should we fix this?", index=0),
            Message(
                role="assistant",
                content="The fix here is to update config.py directly.",
                index=1,
            ),
        ],
        session_id="s1",
    )
    solutions = extract_stated_solutions(transcript)
    assert solutions == []


def test_extract_multiple_trigger_phrases():
    transcript = Transcript(
        messages=[
            Message(role="user", content="Go ahead.", index=0),
            Message(
                role="assistant",
                content=(
                    "Let's update server.py first. "
                    "I will also patch client.py. "
                    "I'm going to run tests in test_server.py."
                ),
                index=1,
            ),
        ],
        session_id="s1",
    )
    solutions = extract_stated_solutions(transcript)
    assert len(solutions) == 3
    assert solutions[0].referenced_paths == ["server.py"]
    assert solutions[1].referenced_paths == ["client.py"]
    assert solutions[2].referenced_paths == ["test_server.py"]


def test_extract_multiple_paths_in_one_sentence():
    transcript = Transcript(
        messages=[
            Message(role="user", content="ok", index=0),
            Message(
                role="assistant",
                content="I'll update both models.py and schema.py to match.",
                index=1,
            ),
        ],
        session_id="s1",
    )
    solutions = extract_stated_solutions(transcript)
    assert len(solutions) == 1
    assert solutions[0].referenced_paths == ["models.py", "schema.py"]
