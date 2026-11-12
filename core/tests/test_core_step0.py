"""The step-0 list as the model's own first turn (study flag AETHER_CORE_STEP0_FILE)."""

import json

import pytest

from aether.core import step0
from aether.core.responses import input_items

TAIL = "(Working directory: /app. Time limit: 900s.)"


def test_no_record_keeps_the_single_task_message():
    assert step0.task_messages("", "Do X.", "", TAIL) == [{"role": "user", "content": f"Do X.\n\n{TAIL}"}]
    assert step0.task_messages("", "Do X.", "\n\nextra", TAIL) == [{"role": "user", "content": f"Do X.\n\nextra\n\n{TAIL}"}]


def test_record_becomes_question_own_answer_then_go(tmp_path):
    path = tmp_path / "s0.json"
    path.write_text(json.dumps({"question": "List the open points.\n\n", "answer": " a -> MACHINE: look\n"}), encoding="utf-8")
    messages = step0.task_messages(str(path), "Do X.", "", TAIL)
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[0]["content"] == "List the open points.\n\nDo X."
    assert messages[1]["content"] == "a -> MACHINE: look"  # the model's words only, in the model's turn
    assert messages[2]["content"] == f"{step0.GO}\n\n{TAIL}"
    assert "MACHINE" not in messages[0]["content"] + messages[2]["content"]  # the list is in no user message


def test_record_reaches_the_provider_as_an_assistant_item(tmp_path):
    path = tmp_path / "s0.json"
    path.write_text(json.dumps({"question": "Q", "answer": "A"}), encoding="utf-8")
    items = input_items([{"role": "system", "content": "S"}, *step0.task_messages(str(path), "T", "", TAIL)])
    assert {"role": "assistant", "content": "A"} in items
    assert [i.get("role") for i in items if i.get("role") in ("user", "assistant")] == ["user", "assistant", "user"]


@pytest.mark.parametrize("record", [{"question": "", "answer": "A"}, {"question": "Q", "answer": "  "}])
def test_empty_record_is_refused(tmp_path, record):
    path = tmp_path / "s0.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError):
        step0.task_messages(str(path), "T", "", TAIL)
