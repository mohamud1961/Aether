"""Text turns (``turn="json"``): the model acts by writing one JSON object instead of native tool calls.

Every reply carries a written analysis and plan with its actions, as in Terminus 2's interface, and the request
has no tools parameter. The same tools run through the same validation; only the interface changes. A reply that
cannot be read as an action is answered with the parse problem, never silently dropped (see ``read_reply``).
"""

from __future__ import annotations

import json
from typing import Any

REPLY_DOC = """

Reply format: there is no function-calling interface. Every reply is exactly one JSON object, nothing else:
{"analysis": "...", "plan": "...", "actions": [{"tool": "<tool name>", "args": {...}}], "task_complete": false}
- analysis: what the latest results show, including anything in them that contradicts what you expected or what \
the task requires; where the task stands against each of its requirements, and what has been verified and how.
- plan: what you will do next and the result you expect.
- actions: tool calls, run in order; all their results come back in the next message. String arguments are \
JSON strings (escape newlines and quotes).
- task_complete: true ends the work after any actions in this reply have run. Set it only when every \
requirement is met and checked, or when no time is left.
The tools and their arguments (* = required):
"""


def reply_doc(tools: list[dict[str, Any]]) -> str:
    lines = []
    for spec in tools:
        fn = spec["function"]
        if fn["name"] == "finish":
            continue  # task_complete ends the work in this format
        props = fn["parameters"].get("properties", {})
        required = set(fn["parameters"].get("required", ()))
        args = ", ".join(
            f"{name}{'*' if name in required else ''}: {rule.get('type', 'any')}"
            + (f" ({rule['description']})" if rule.get("description") else "")
            + (f" one of {rule['enum']}" if rule.get("enum") else "")
            for name, rule in props.items()
        )
        lines.append(f"- {fn['name']}({args}): {fn['description']}")
    return REPLY_DOC + "\n".join(lines)


REPAIR_STEPS = 12


def _repair(text: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Mend the two slips S5's unreadable replies showed (10 of 12 with content): an action object left unclosed,
    and a double quote left unescaped inside a string. Each step must parse or move the error later; the edits
    are reported to the model. Returns (object, edits) or (None, [])."""
    decoder = json.JSONDecoder(strict=False)
    edits: list[str] = []
    for _ in range(REPAIR_STEPS):
        try:
            obj = decoder.decode(text)
            return (obj, edits) if isinstance(obj, dict) else (None, [])
        except json.JSONDecodeError as exc:
            pos = exc.pos
        options = []
        comma = text.rfind(",", 0, pos)
        close_here = (f"added '}}' at character {pos}", text[:pos] + "}" + text[pos:])
        close_before = (
            f"added '}}' at character {comma}",
            text[:comma] + "}" + text[comma:],
        )
        if pos < len(text) and text[pos] in "]}":
            options.append(close_here)
        if comma > 0:
            options.append(close_before)
        if close_here not in options:
            options.append(close_here)
        quote = text.rfind('"', 0, pos)
        while quote > 0 and text[quote - 1] == "\\":
            quote = text.rfind('"', 0, quote - 1)
        if quote > 0:
            options.append(
                (
                    f"escaped the quote at character {quote}",
                    text[:quote] + "\\" + text[quote:],
                )
            )
        chosen = None
        for note, candidate in options:
            try:
                decoder.decode(candidate)
                chosen = (note, candidate)
                break
            except json.JSONDecodeError as later:
                if later.pos > pos + 1:
                    chosen = (note, candidate)
                    break
        if chosen is None:
            return None, []
        edits.append(chosen[0])
        text = chosen[1]
    return None, []


def read_reply(content: str) -> tuple[dict[str, Any] | None, str, str]:
    """(object, protocol class, problem or repair note). Classes: strict (the reply is one object, code fences
    allowed; literal newlines inside strings are accepted), repaired (see ``_repair``; the note lists the edits),
    embedded (an object found inside other text; accepted), invalid (no usable object; the problem says where it
    broke so the model can fix it)."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("\n") + 1 :] if "\n" in text else ""
    decoder = json.JSONDecoder(strict=False)
    try:
        obj = decoder.decode(text)
        if isinstance(obj, dict):
            return obj, "strict", ""
        problem = "the reply is JSON but not an object"
    except json.JSONDecodeError as exc:
        if "{" not in text:
            problem = "the reply has no JSON object (it must be only the JSON object, with your text in analysis)"
        else:
            near = text[max(0, exc.pos - 80) : exc.pos + 20].replace("\n", "\\n")
            problem = (
                f"not valid JSON ({exc.msg} at character {exc.pos}, here: ...{near}...). Inside a JSON string "
                'every double quote must be written \\" and every backslash \\\\. For long file contents, '
                "use a reply whose only action writes that file"
            )
    start = text.find("{")
    while start != -1:
        try:
            obj, _ = decoder.raw_decode(text[start:])
            if isinstance(obj, dict) and ("actions" in obj or "task_complete" in obj):
                return obj, "embedded", ""
        except json.JSONDecodeError:
            pass
        start = text.find("{", start + 1)
    if text.startswith("{"):
        obj, edits = _repair(text)
        if obj is not None and ("actions" in obj or "task_complete" in obj):
            return (
                obj,
                "repaired",
                (
                    "your reply was not valid JSON and was mended before running ("
                    + "; ".join(edits)
                    + "); check below that each action ran as you intended"
                ),
            )
    return None, "invalid", problem


def calls_from(obj: dict[str, Any], turn_no: int) -> tuple[list[dict[str, Any]], str]:
    """Native-shaped calls for the reply's actions (then ``finish`` when task_complete), or a problem to report."""
    actions = obj.get("actions", [])
    if not isinstance(actions, list):
        return [], '"actions" must be a list'
    calls = []
    for i, act in enumerate(actions):
        if (
            not isinstance(act, dict)
            or not isinstance(act.get("tool"), str)
            or not isinstance(act.get("args", {}), dict)
        ):
            return [], f'action {i + 1} must be {{"tool": "<name>", "args": {{...}}}}'
        calls.append(_call(turn_no, i, act["tool"], act.get("args", {})))
    if obj.get("task_complete") is True and not any(
        c["function"]["name"] == "finish" for c in calls
    ):
        calls.append(
            _call(
                turn_no, len(calls), "finish", {"summary": str(obj.get("analysis", ""))}
            )
        )
    return (
        calls,
        "" if calls else "the reply has no actions and task_complete is not true",
    )


def _call(turn_no: int, i: int, name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"t{turn_no}a{i + 1}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def results_message(
    rows: list[tuple[str, str]], clock: str, note: str = ""
) -> dict[str, Any]:
    """All of one reply's results, in order, as the next user message (after a repair note, when there is one)."""
    parts = [
        f"Result of action {i + 1} ({name}):\n{out}"
        for i, (name, out) in enumerate(rows)
    ]
    head = f"[{note}]\n\n" if note else ""
    return {"role": "user", "content": head + "\n\n".join(parts) + f"\n{clock}"}


def problem_message(problem: str, clock: str) -> dict[str, Any]:
    return {
        "role": "user",
        "content": f"Your reply could not be run: {problem}. Reply with exactly one JSON object in the "
        f"required format. {clock}",
    }
