"""T1 (audit, 15 Nov): what the model emits is what each tool's receiver gets, or the call is refused before any effect.

Hop by hop, on real Linux processes: the model's arguments as provider JSON -> ``parse_arguments`` -> the owner
(terminal, python REPL, file write, MCP client) -> the receiver's own parser, which writes what it received to a file:
bash reading a quoted here-document, the Python compiler reading a string literal, the kernel writing file bytes, and
an MCP server's JSON parser. The payloads are the shapes where transports are known to alter calls (Unicode, tabs,
CR, backslashes, shell metacharacters, escapes, here-document lookalikes, NUL, over-long text, unencodable text).

Contract per payload and tool: the received bytes equal the emitted text, or the tool says plainly it did not send it
and nothing ran. Falsifier: received bytes differ while the tool reports success (a silent alteration), or a refused
call leaves the tool in a state that blocks or misreports the next call.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from aether.core.files import Files
from aether.core.mcp import Mcp
from aether.core.provider import parse_arguments
from aether.core.repl import Repl
from aether.core.terminal import Terminals
from tests.core_fakes import LocalEnv

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")
FIXTURE = str(Path(__file__).with_name("mcp_fixture_server.py"))

PAYLOADS = {
    "unicode": "h\u00e9llo \u2014 \u4e16\u754c \U0001f680 zero\u200bwidth",
    "tabs_cr": "a\tb\r\nc\rd",
    "backslashes": "C:\\path\\n\\t \\x41 \\\\ \\u00e9 end",
    "shell_meta": "$HOME `id` $(whoami) ${X:-y} !! !$ * ? [a] ~ ; & | > <",
    "quotes": "'single' \"double\" ''' \"\"\" \\' \\\"",
    "heredoc_lookalike": "EOF\n<<EOF\nT1EOFX\n  T1EOF",
    "control_chars": "\x1b[31mred\x1b[0m \x07 \x03 \x7f",
    "json_nested": json.dumps({"a": [1, {"b": "c\"d"}], "e": "\\u00e9", "f": "\n"}),
    "leading_dash": "-n -e --help",
    "trailing_whitespace": "spaces   \n\n\t\n",
    "long": ("0123456789abcdef" * 16384)[:200_000],  # past the terminal's inline argv cap
    "nul": "before\x00after",
    "lone_surrogate": "ok \ud800 bad",
}


def emitted(args: dict) -> dict:
    """Hop 1: the provider's JSON arguments string, decoded as the loop decodes it."""
    return parse_arguments(json.dumps(args))


def received(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def expect(owner: str, text: str) -> bytes | None:
    """The bytes the receiver should hold. Python and MCP carry the text escaped (a string literal, JSON), so even an
    unpaired surrogate arrives as itself; a shell or a file needs real UTF-8 bytes."""
    try:
        return text.encode("utf-8", "surrogatepass" if owner in ("python", "mcp") else "strict")
    except UnicodeEncodeError:
        return None


# The only refusals allowed: text with no bytes for that receiver. Every other payload must arrive exactly.
MAY_REFUSE = {"terminal": {"nul", "lone_surrogate"}, "file": {"lone_surrogate"}, "python": set(), "mcp": set()}


async def via_terminal(tmp_path: Path, name: str, text: str) -> tuple[bytes | None, str, str]:
    """Bash reads a quoted here-document: no expansion, so its bytes are the command's bytes."""
    got = tmp_path / f"term-{name}"
    ctrl = Terminals(LocalEnv(tmp_path), str(tmp_path), lambda: 1000.0, control_dir=str(tmp_path / "ctl"),
                     preserve_existing=True)
    try:
        args = emitted({"name": "t1", "input": f"cat > {got} <<'T1EOF'\n{text}\nT1EOF"})
        try:
            out = await ctrl.use(name=args["name"], input=args["input"], wait_s=10)
        except Exception as exc:
            out = f"error: {type(exc).__name__}: {exc}"
        after = await ctrl.use(name="t1", input="echo T1-NEXT-OK", wait_s=10)  # the tool still works afterwards
        data = received(got)
        return (data[:-1] if data is not None and data.endswith(b"\n") else data), out, after
    finally:
        await ctrl.close()


async def via_python(tmp_path: Path, name: str, text: str) -> tuple[bytes | None, str, str]:
    """The Python compiler reads a string literal: any changed byte of the cell source changes the decoded value."""
    got = tmp_path / f"py-{name}"
    repl = Repl(LocalEnv(tmp_path), str(tmp_path), lambda: 600.0, None, base=str(tmp_path / f"repl-{name}"),
                track_operations=True)
    assert await repl.start()
    try:
        code = f"open({str(got)!r}, 'w', encoding='utf-8', errors='surrogatepass', newline='').write({text!r})"
        args = emitted({"code": code})
        try:
            out = await repl.run(args["code"], wait_s=10)
        except Exception as exc:
            out = f"error: {type(exc).__name__}: {exc}"
        after = await repl.run("print('T1-NEXT-' + 'OK')", wait_s=10)
        return received(got), out, after
    finally:
        await repl.close()


async def via_file(tmp_path: Path, name: str, text: str) -> tuple[bytes | None, str, str]:
    got = tmp_path / f"file-{name}"
    files = Files(LocalEnv(tmp_path), str(tmp_path))
    args = emitted({"path": str(got), "content": text})
    try:
        out = await files.write(args["path"], args["content"])
    except Exception as exc:
        out = f"error: {type(exc).__name__}: {exc}"
    after = await files.write(str(tmp_path / f"file-{name}-next"), "T1-NEXT-OK")
    return received(got), out, after


async def via_mcp(tmp_path: Path, name: str, text: str) -> tuple[bytes | None, str, str]:
    got = tmp_path / f"mcp-{name}"
    spec = {"name": "fx", "transport": "stdio", "url": None, "command": sys.executable, "args": [FIXTURE, "stdio"]}
    mcp = Mcp(LocalEnv(tmp_path), str(tmp_path / f"mcp-control-{name}"), [spec])
    try:
        args = emitted({"server": "fx", "action": "call", "tool": "record",
                        "arguments": {"path": str(got), "text": text}, "timeout_s": 30})
        try:
            out = await mcp.use(args, 120)
        except Exception as exc:
            out = f"error: {type(exc).__name__}: {exc}"
        after = await mcp.use({"server": "fx", "action": "call", "tool": "count", "timeout_s": 30}, 120)
        return received(got), out, after
    finally:
        await mcp.close()


OWNERS = {"terminal": via_terminal, "python": via_python, "file": via_file, "mcp": via_mcp}
NEXT_OK = {"terminal": "T1-NEXT-OK", "python": "T1-NEXT-OK", "file": "wrote 10 bytes", "mcp": "count=1"}


def classify(owner: str, name: str, text: str, data: bytes | None, out: str, after: str) -> str:
    if NEXT_OK[owner] not in after:
        return f"next call broken: {after[-200:]!r}"
    want = expect(owner, text)
    if data is not None and data == want:
        return "exact"
    if data is None and name in MAY_REFUSE[owner] and out.startswith("error") and "nothing ran" in out:
        return "refused"
    return f"ALTERED: received {data[:80] if data else data!r} for {want[:80] if want else want!r}; told {out[-200:]!r}"


@pytest.mark.parametrize("owner", sorted(OWNERS))
def test_every_payload_arrives_exactly_or_is_refused_before_any_effect(tmp_path, owner):
    results = {}
    for name, text in PAYLOADS.items():
        if owner == "terminal" and "\nT1EOF\n" in f"\n{text}\n":
            continue
        case = tmp_path / name
        case.mkdir()
        data, out, after = asyncio.run(OWNERS[owner](case, name, text))
        results[name] = classify(owner, name, text, data, out, after)
    print(f"T1-{owner}", json.dumps(results, ensure_ascii=True))
    bad = {k: v for k, v in results.items() if v not in ("exact", "refused")}
    assert not bad, bad


def test_the_classifier_catches_a_silent_alteration():
    """Known-bad: a receiver that got different bytes while the tool reported success is never 'exact'."""
    assert classify("file", "tabs", "a\tb", b"a    b", "wrote 6 bytes (1 lines)", "wrote 10 bytes").startswith("ALTERED")
    assert classify("file", "x", "x", b"x", "wrote 1 bytes", "error: broken").startswith("next call broken")
    # A refusal counts only where the text has no bytes for that receiver, and only when it says nothing ran.
    assert classify("terminal", "tabs", "a\tb", None, "error: nothing ran", "T1-NEXT-OK").startswith("ALTERED")
    assert classify("terminal", "nul", "a\x00", None, "error: failed", "T1-NEXT-OK").startswith("ALTERED")
