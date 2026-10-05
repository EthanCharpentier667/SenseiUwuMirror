"""Tests for the ``sensai.react`` module."""

from typing import Any

import pytest

from sensai.react import FINAL_ANSWER, Decision, ReActController


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

    assert list(schema["properties"]) == ["thought", "missing", "action", "args"]
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
            (
                '{"thought": " look it up ", "missing": " names ", "action": "web_search", '
                '"args": {"query": "x"}}'
            ),
            Decision("look it up", "web_search", {"query": "x"}, "names"),
        ),
        (
            '{"thought": "t", "action": "web_search", "args": {"query": "x", "thought": "t"}}',
            Decision("t", "web_search", {"query": "x"}),
        ),
        (
            '{"thought": "t", "action": "nope", "args": {"a": 1}}',
            Decision("t", "nope", {"a": 1}),
        ),
        ('{"thought": "t", "action": "web_search", "args": "bad"}', Decision("t", "web_search")),
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


def test_plan_instructions_describe_tools_and_steps() -> None:
    controller = ReActController([SEARCH, COUNT])
    assert "(none yet)" in controller.plan_instructions()

    controller.record(Decision("t", "web_search", {"query": "fox"}), "done", "A fox.")
    instructions = controller.plan_instructions()

    assert "- web_search(query: string): The web_search tool." in instructions
    assert "- count(n: integer, unit: string (optional)): The count tool." in instructions
    assert f"- {FINAL_ANSWER}(): " in instructions
    assert '1. web_search {"query": "fox"} -> done\n   A fox.' in instructions


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
    ("decision", "finishes", "draft"),
    [
        (Decision("t", FINAL_ANSWER, missing="nothing"), True, None),
        (Decision("t", FINAL_ANSWER, missing="the names"), True, None),
        (Decision("t", "web_search", {"query": "a"}, "the names"), False, None),
        (Decision("The answer.", "web_search", {"query": "a"}, "Nothing."), True, "The answer."),
        (Decision("The answer.", "web_search", {"query": "a"}, ""), True, "The answer."),
        (Decision("", "web_search", {"query": "a"}, "none"), True, None),
    ],
)
def test_finishes_when_final_answer_or_nothing_missing(
    decision: Decision,
    finishes: bool,  # noqa: FBT001 - pytest parameter
    draft: str | None,
) -> None:
    controller = ReActController([SEARCH])

    assert controller.finishes(decision) is finishes
    assert controller.draft == draft


def test_answer_instructions_carry_the_draft() -> None:
    controller = ReActController([SEARCH])
    controller.finishes(Decision("Ten names: A, B.", "web_search", {"query": "a"}, "nothing"))

    instructions = controller.answer_instructions() or ""

    assert "Ten names: A, B." in instructions
    assert "Information gathered with tools" not in instructions
