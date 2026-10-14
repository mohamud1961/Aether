"""What the model is told and the tools it is offered."""

from __future__ import annotations

from typing import Any
import math

from .clm import HISTORY_PATH, MIRROR_PATH
from .terminal import MAX_WAIT_S

BASE_PROMPT = """You are an expert engineer working autonomously in a Linux container to complete the task \
you are given. No one will answer questions; keep working until the task is done.

Your tools:
- terminal: persistent bash shells. The working directory, environment variables, virtualenvs and running \
programs persist between calls. Open several named terminals to run things in parallel (for example a long \
build in one while you explore in another). For long-running commands (builds, test runs), run them in the \
foreground with a wait_s: the call returns as soon as the command finishes, and if it is still running you can \
wait again or interrupt it. That is faster than `cmd & sleep N`, which always waits the full N seconds. Each \
terminal keeps its full output in a log file; large outputs are shown as head and tail with the log path, so \
grep or tail the log instead of re-running.
- read_file, write_file, edit_file: read with line numbers, create or replace files, and make exact edits.
{python}{images}- finish: end the task.
{context}
Working well:
- Look at what exists before changing it, and keep to what the task asks; do not alter or delete unrelated \
files, history or system state.
- Check your work the way the task will be judged: run the real program and confirm the exact output, file \
location, name and format the task requires. For anything you produce (images, binaries, data files, \
rendered output), check its content, not only that it exists or has the right header: decode it and \
measure whether it is what the task describes.
- Unexplained output (garbled characters, error messages, warnings, odd values) means something is wrong \
until you have explained it. So does an unexplained duration: a program that runs until your timeout kills \
it, when you expected it to finish or exit, is hung or looping; find out why rather than raising the timeout.
- Every tool result shows the elapsed time and the time limit. Get a complete working result early, then \
improve it.
- Call finish only when every requirement is met and checked, or when no time is left."""

PYTHON_DOC = """- python: a persistent Python {version} REPL inside the container. Variables, imports and functions \
persist between calls, so you can load data once and work on it, and build your own tools (parsers, \
checkers, test harnesses, image or binary analysis) as functions you reuse. Built in: sh(cmd) -> result with \
.code and .output; read(path); read_bytes(path); write(path, text_or_bytes); edit(path, old, new); and \
llm(prompt) -> str, which asks a sub-model (no tools) so you can have large data held in variables \
summarised or searched without putting it into your own context. The value of a final expression is \
printed. Long cells keep running: use wait_s and call again with empty code to keep waiting.
"""

IMAGES_DOC = """- view_image: look at an image file (PNG, JPEG, BMP, PPM, GIF, ...). Use it to check visual output \
you produce, such as a rendered frame, plot or screenshot, against what the task describes.
"""

CLM_DOC = f"""
Your context: everything after the task statement is your working context. It has a token budget, and it \
is mirrored at {MIRROR_PATH}, one [[CTX_TURN i role=...]] block per message. You manage it yourself: \
condense it by editing that file with your normal tools (keep facts, paths, decisions, results and open \
problems; drop stale output). When you edit it, the edited file replaces your earlier history (the task \
statement stays). Files and terminal logs on disk are never affected by this. Before discarding history, the \
harness saves original appended messages in {HISTORY_PATH} ([[MSG n role=...]] blocks containing JSON). \
The edit/checkpoint receipt confirms that path or reports a save failure. Grep the saved file to recover an \
old observation; do not assume a failed save left a usable copy. read_history retrieves an original \
message by MSG number even when that file cannot be written; it supports bounded character pages.
"""

TERMINAL = {
    "type": "function",
    "function": {
        "name": "terminal",
        "description": "Send input to a persistent bash terminal and return its new output. mode=command (default) "
        "runs the input as shell command(s) and waits up to wait_s for them to finish; mode=keys "
        "sends raw keystrokes to whatever is running (e.g. an interactive program; \\x03 is Ctrl-C) "
        "and returns once output settles. Empty input just waits for and shows new output.",
        "parameters": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "Command(s) or keystrokes. May be empty.",
                },
                "name": {
                    "type": "string",
                    "description": "Terminal name (default 'main'); a new name opens a new terminal.",
                },
                "mode": {"type": "string", "enum": ["command", "keys"]},
                "wait_s": {
                    "type": "number",
                    "description": f"Max seconds to wait (default 30, max {MAX_WAIT_S:.0f}); "
                    "call again to keep waiting.",
                },
                "interrupt": {
                    "type": "boolean",
                    "description": "Send Ctrl-C to the running program first.",
                },
            },
            "required": ["input"],
        },
    },
}
PYTHON = {
    "type": "function",
    "function": {
        "name": "python",
        "description": "Run Python code in the persistent REPL and return its output. Empty code waits for a "
        "running cell; interrupt=true stops it.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python source. May be empty.",
                },
                "wait_s": {
                    "type": "number",
                    "description": f"Max seconds to wait (default 60, max {MAX_WAIT_S:.0f}); "
                    "call again to keep waiting.",
                },
                "interrupt": {
                    "type": "boolean",
                    "description": "Interrupt the running cell first.",
                },
            },
            "required": ["code"],
        },
    },
}
READ_FILE = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a text file with line numbers (default 400 lines from start_line).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "num_lines": {"type": "integer"},
                "offset": {
                    "type": "integer",
                    "description": "Byte offset into the numbered line selection; use next_offset from a clipped page.",
                },
            },
            "required": ["path"],
        },
    },
}
WRITE_FILE = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Create or overwrite a file with the given content (parents are created; permissions kept).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
}
EDIT_FILE = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": "Replace an exact, unique occurrence of old_str with new_str in a file "
        "(or every occurrence with replace_all=true).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string"},
                "new_str": {"type": "string"},
                "replace_all": {"type": "boolean"},
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
}
VIEW_IMAGE = {
    "type": "function",
    "function": {
        "name": "view_image",
        "description": "Look at an image file in the environment; the image is shown to you after the tool result.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
}
FINISH = {
    "type": "function",
    "function": {
        "name": "finish",
        "description": "End the task. Use when every requirement is met and checked, or no time is left.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "One or two sentences on the final state.",
                },
            },
            "required": ["summary"],
        },
    },
}
# The verifier's finish (see verify): a verdict on the state it checked, with the evidence.
VERDICT_FINISH = {
    "type": "function",
    "function": {
        "name": "finish",
        "description": "End the check with your verdict on the current state.",
        "parameters": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["confirmed", "refuted"]},
                "evidence": {
                    "type": "string",
                    "description": "What you checked and what you found. For refuted: what is wrong, how you "
                    "established it, and the correct result if you know it.",
                },
            },
            "required": ["verdict", "evidence"],
        },
    },
}
# Self-check before finishing (arm B). The L1/L2 wrong finishes rested on checks that reused the solver's own
# assumption (an example address, its own Tm definition, a substituted sequence), so they could not fail.
SELF_CHECK_DOC = """
Before you finish: name the facts your result rests on that you did not observe directly (values taken from an \
example in the task, definitions or conventions you chose where the task leaves them open, data from a source \
you picked, anything only a check you wrote supports). Check the riskiest of them against something you did not \
write: the task's own files and data, the real program's behaviour, an authoritative source. For each check ask \
whether it could have failed if you were wrong; one that reuses your own assumption cannot. Do not repeat checks \
that already passed; then finish."""


# Turn modes: "tool" replies may be a bare tool call; "analysis" asks for written analysis before every action
# (with tool_choice "auto"; a forced tool call suppressed the writing in the S2 replay); "json" replaces native
# tool calls with one written JSON object per reply (see textturn).
TURN_MODES = ("tool", "analysis", "json")
ANALYSIS_DOC = """
Every reply: before your tool call, write in the reply text (1) what the latest results show, including anything \
in them that contradicts what you expected or what the task requires; (2) where the task stands against each of \
its requirements, and what has been verified and how; (3) what you will do next and the result you expect. \
Then make the call."""


def system_prompt(
    *,
    python_version: str,
    clm: bool,
    images: bool = False,
    mirror_path: str = MIRROR_PATH,
    history_path: str = HISTORY_PATH,
    turn: str = "tool",
    self_check: bool = False,
) -> str:
    context = CLM_DOC.replace(MIRROR_PATH, mirror_path).replace(
        HISTORY_PATH, history_path
    )
    if turn not in TURN_MODES:
        raise ValueError(f"turn must be one of {TURN_MODES}")
    return (
        BASE_PROMPT.format(
            python=PYTHON_DOC.format(version=python_version) if python_version else "",
            images=IMAGES_DOC if images else "",
            context=context if clm else "",
        )
        + (SELF_CHECK_DOC if self_check else "")
        + (ANALYSIS_DOC if turn == "analysis" else "")
    )


RUN_CHECKS = {
    "type": "function",
    "function": {
        "name": "run_checks",
        "description": "Run the acceptance checks on a disposable copy of the current state and report each result. "
        "Nothing they do reaches the real state. They are fallible; the task text decides.",
        "parameters": {"type": "object", "properties": {}},
    },
}


READ_HISTORY = {
    "type": "function",
    "function": {
        "name": "read_history",
        "description": "Read an original CLM history message by stable MSG number, including removed messages. "
        "Works even if HISTORY.txt could not be saved. A page states the next character offset.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {"type": "integer"},
                "offset": {"type": "integer"},
                "limit": {
                    "type": "integer",
                    "description": "Characters per page, 1..20000; default 12000.",
                },
            },
            "required": ["message_id"],
        },
    },
}


def tools(
    *,
    python: bool,
    images: bool = False,
    contract: bool = False,
    history: bool = False,
    verdict: bool = False,
) -> list[dict[str, Any]]:
    return [
        TERMINAL,
        *([PYTHON] if python else []),
        READ_FILE,
        WRITE_FILE,
        EDIT_FILE,
        *([VIEW_IMAGE] if images else []),
        *([RUN_CHECKS] if contract else []),
        *([READ_HISTORY] if history else []),
        VERDICT_FINISH if verdict else FINISH,
    ]


def validate_call(
    name: str, arguments: dict[str, Any], definitions: list[dict[str, Any]]
) -> None:
    """Validate the advertised flat tool contract before any effect; never coerce an invalid value."""
    fn = next(
        (d["function"] for d in definitions if d["function"]["name"] == name), None
    )
    if fn is None:
        raise ValueError(
            f"unknown tool {name!r} (or unavailable in this run); use an advertised tool"
        )
    schema = fn["parameters"]
    missing = set(schema.get("required", ())) - arguments.keys()
    if missing:
        raise ValueError(
            f"{name}: missing required arguments: {', '.join(sorted(missing))}"
        )
    properties = schema.get("properties", {})
    for key, value in arguments.items():
        if key not in properties:
            raise ValueError(
                f"{name}: unknown argument {key!r}; allowed: {', '.join(properties)}"
            )
        rule = properties[key]
        kind = rule["type"]
        valid = {
            "string": isinstance(value, str),
            "boolean": type(value) is bool,
            "integer": type(value) is int,
            "number": type(value) in (int, float) and math.isfinite(value),
        }.get(kind, False)
        if not valid:
            raise ValueError(
                f"{name}.{key}: expected {kind}, got {type(value).__name__}"
            )
        if "enum" in rule and value not in rule["enum"]:
            raise ValueError(f"{name}.{key}: expected one of {rule['enum']}")
