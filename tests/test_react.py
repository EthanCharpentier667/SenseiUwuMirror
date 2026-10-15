"""Tests for the ``sensai.features.react.react`` module."""

from typing import Any

import pytest

from sensai.features.react.react import FINAL_ANSWER, Decision, ReActController


def _definition(name: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"The {name}\n tool.",
            "parameters": {"type": "object", "required": required, "properties": properties},
        },
    }


SEARCH = _definition("web_search", {"query": {"type": "string"}}, ["query"])
COUNT = _definition("count", {"n": {"type": "integer"}, "unit": {"type": "string"}}, ["n"])


def test_schema_puts_thought_first_and_lists_allowed_actions() -> None:
    controller = ReActController([SEARCH, COUNT])

    schema = controller.schema()

    assert list(schema["properties"]) == ["thought", "action", "args"]
    assert schema["properties"]["action"]["enum"] == ["web_search", "count", FINAL_ANSWER]


def test_tool_with_spent_budget_is_no_longer_allowed() -> None:
    controller = ReActController([SEARCH], max_calls_per_tool=1)
    controller.record(Decision("t", "web_search", {"query": "a"}), "done", "result")

    assert controller.allowed_actions() == [FINAL_ANSWER]
    assert "'web_search' is not available now" in (
        controller.check(Decision("t", "web_search", {"query": "b"})) or ""
    )


def test_failed_or_refused_calls_do_not_spend_budget() -> None:
    controller = ReActController([SEARCH], max_calls_per_tool=1)
    controller.record(Decision("t", "web_search", {"query": "a"}), "failed", "Error")
    controller.record(Decision("t", "web_search", {"query": "b"}), "refused", "No")

    assert controller.allowed_actions() == ["web_search", FINAL_ANSWER]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            ('{"thought": " look it up ", "action": "web_search", "args": {"query": "x"}}'),
            Decision("look it up", "web_search", {"query": "x"}),
        ),
        (
            '{"thought": "t", "action": "web_search", "args": {"query": "x", "thought": "t"}}',
            Decision("t", "web_search", {"query": "x"}),
        ),
        (
            '{"thought": "t", "action": "nope", "args": {"a": 1}}',
            Decision("t", "nope", {"a": 1}),
        ),
        (
            '{"thought": "t", "action": "final_answer", "args": {"message": "Voici..."}}',
            Decision("t", FINAL_ANSWER),
        ),
        ('{"thought": "t", "action": "web_search", "args": "bad"}', Decision("t", "web_search")),
        (
            'Ok:\n```json\n{"thought": "t", "action": "web_search", "args": {"query": "x"}}\n```',
            Decision("t", "web_search", {"query": "x"}),
        ),
        (
            '{"thought": "t", "action": "web_search", "args": {"query": "x"}}}',
            Decision("t", "web_search", {"query": "x"}),
        ),
        ("", Decision("", FINAL_ANSWER)),
        ("plain text", Decision("plain text", FINAL_ANSWER)),
        ("[1, 2]", Decision("[1, 2]", FINAL_ANSWER)),
    ],
)
def test_parse(raw: str, expected: Decision) -> None:
    assert ReActController([SEARCH]).parse(raw) == expected


@pytest.mark.parametrize(
    ("decision", "error"),
    [
        (Decision("t", "count", {"n": 3}), None),
        (Decision("t", "count", {"n": 3, "unit": "kg"}), None),
        (Decision("t", "count", {}), "missing argument(s): n."),
        (Decision("t", "count", {"n": "3"}), "argument 'n' must be of type integer."),
        (Decision("t", "count", {"n": True}), "argument 'n' must be of type integer."),
        (Decision("t", "nope", {}), "'nope' is not available now."),
    ],
)
def test_check_validates_action_and_arguments(decision: Decision, error: str | None) -> None:
    result = ReActController([SEARCH, COUNT]).check(decision)

    if error is None:
        assert result is None
    else:
        assert result is not None
        assert result.startswith(error)


def test_check_rejects_a_repeated_call_but_not_a_rejected_one() -> None:
    controller = ReActController([SEARCH])
    controller.record(Decision("t", "web_search", {"query": "a"}), "rejected", "Rejected")
    assert controller.check(Decision("t", "web_search", {"query": "a"})) is None

    controller.record(Decision("t", "web_search", {"query": "a"}), "done", "result")
    assert "already made at step 2" in (
        controller.check(Decision("t", "web_search", {"query": "a"})) or ""
    )
    assert controller.check(Decision("t", "web_search", {"query": "b"})) is None


def test_record_truncates_long_observations() -> None:
    controller = ReActController([SEARCH], observation_limit=5)
    controller.record(Decision("t", "web_search", {"query": "a"}), "done", "0123456789")

    assert controller.steps[0].observation == "01234… [truncated]"


def test_plan_instructions_describe_the_tools() -> None:
    instructions = ReActController([SEARCH, COUNT]).plan_instructions()

    assert "- web_search(query: string): The web_search tool." in instructions
    assert "- count(n: integer, unit: string (optional)): The count tool." in instructions
    assert f"- {FINAL_ANSWER}(): " in instructions


def test_trajectory_replays_each_action_then_its_observation() -> None:
    controller = ReActController([SEARCH, COUNT])
    assert controller.trajectory() == []

    controller.record(Decision("Look it up.", "web_search", {"query": "fox"}), "done", "A fox.")
    controller.record(Decision("", "count", {}), "rejected", "Rejected: missing argument(s): n.")

    assert controller.trajectory() == [
        {
            "role": "assistant",
            "content": (
                '{"thought": "Look it up.", "action": "web_search", "args": {"query": "fox"}}'
            ),
            "ephemeral": True,
        },
        {
            "role": "tool",
            "tool_name": "web_search",
            "content": "Observation: A fox.",
            "ephemeral": True,
        },
        {
            "role": "assistant",
            "content": '{"thought": "", "action": "count", "args": {}}',
            "ephemeral": True,
        },
        {
            "role": "tool",
            "tool_name": "count",
            "content": "Observation (rejected): Rejected: missing argument(s): n.",
            "ephemeral": True,
        },
    ]


def test_answer_instructions_only_carry_successful_results() -> None:
    controller = ReActController([SEARCH])
    assert controller.answer_instructions() is None

    controller.record(Decision("t", "web_search", {"query": "a"}), "failed", "Error: boom")
    assert controller.answer_instructions() is None

    controller.record(Decision("t", "web_search", {"query": "b"}), "done", "A fox.")
    instructions = controller.answer_instructions() or ""
    assert "A fox." in instructions
    assert "boom" not in instructions


def test_tool_without_parameters_is_described_and_callable() -> None:
    controller = ReActController([{"type": "function", "function": {"name": "ping"}}])

    assert "- ping(): " in controller.plan_instructions()
    assert controller.check(Decision("t", "ping")) is None


def test_total_tool_budget_leaves_only_final_answer() -> None:
    controller = ReActController([SEARCH, COUNT], max_tool_calls=2)
    controller.record(Decision("t", "web_search", {"query": "a"}), "done", "r")
    assert controller.allowed_actions() == ["web_search", "count", FINAL_ANSWER]

    controller.record(Decision("t", "count", {"n": 1}), "done", "r")
    assert controller.allowed_actions() == [FINAL_ANSWER]


@pytest.mark.parametrize(
    ("decision", "finishes"),
    [
        (Decision("Done.", FINAL_ANSWER), True),
        (Decision("Need more.", "web_search", {"query": "a"}), False),
        (Decision("", "unknown"), False),
        (Decision("Again.", "web_search", {"query": "first"}), True),
    ],
)
def test_finishes_on_the_final_answer_or_a_repeated_call(
    decision: Decision,
    finishes: bool,  # noqa: FBT001 - pytest parameter
) -> None:
    controller = ReActController([SEARCH])
    controller.record(Decision("t", "web_search", {"query": "first"}), "done", "result")

    assert controller.finishes(decision) is finishes


def test_exhausted_once_no_tool_can_run() -> None:
    controller = ReActController([SEARCH], max_calls_per_tool=1)
    assert not controller.exhausted()

    controller.record(Decision("t", "web_search", {"query": "a"}), "failed", "Error")
    assert not controller.exhausted()

    controller.record(Decision("t", "web_search", {"query": "b"}), "done", "r")
    assert controller.exhausted()


def test_images_only_come_from_done_steps_and_are_noted_in_the_observation() -> None:
    controller = ReActController([SEARCH], observation_limit=5)
    controller.record(Decision("t", "web_search", {"query": "a"}), "done", "0123456789", ["i1"])
    controller.record(Decision("t", "web_search", {"query": "b"}), "failed", "Error", ["i2"])
    controller.record(Decision("t", "web_search", {"query": "c"}), "done", "r")

    assert controller.images() == ["i1"]
    assert controller.steps[0].observation == (
        "01234… [truncated]\n[1 image(s) from this tool are attached to the user's latest message.]"
    )
    assert controller.steps[2].observation == "r"


def test_json_instructions_spell_out_the_allowed_actions() -> None:
    instructions = ReActController([SEARCH]).json_instructions()

    assert f'"action": "<one of: web_search, {FINAL_ANSWER}>"' in instructions
