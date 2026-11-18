"""A failed tool must falsify the sustained episode qualification gate."""

import importlib.util
import json
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[1] / "qa" / "sustained_core.py"
    spec = importlib.util.spec_from_file_location("sustained_qualification", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize(
    "name,args",
    [
        ("view_image", {"path": "pixel.ppm"}),
        ("write_file", {"path": "artifact.txt", "content": "draft"}),
        ("edit_file", {"path": "artifact.txt", "old_str": "draft", "new_str": "fixed"}),
    ],
)
def test_sustained_gate_rejects_a_failed_required_tool(name, args):
    action = {"id": "soak-0", "function": {"name": name, "arguments": json.dumps(args)}}
    rows = [
        {"event": "model", "tool_calls": [action]},
        {
            "event": "tool",
            "name": name,
            "args": args,
            "result": "error: injected tool failure",
        },
    ]
    with pytest.raises(RuntimeError):
        module().validate_trace(rows, [("soak-0", name, args)])
