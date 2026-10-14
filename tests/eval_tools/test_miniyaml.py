from __future__ import annotations

import pytest

from harness_evals.miniyaml import MiniYamlError, parse


def test_scalars_are_typed():
    data = parse("name: demo\ncount: 30\nflag: true\nother: false\nquoted: \"a: b # c\"\n")
    assert data == {"name": "demo", "count": 30, "flag": True, "other": False, "quoted": "a: b # c"}


def test_block_and_inline_lists():
    text = "outputs:\n  - a.txt\n  - 'b c.txt'\ntags: [x, \"y, z\", 3]\nempty: []\nnone_given:\n"
    data = parse(text)
    assert data["outputs"] == ["a.txt", "b c.txt"]
    assert data["tags"] == ["x", "y, z", 3]
    assert data["empty"] == []
    assert data["none_given"] == []


def test_comments_full_line_and_trailing():
    text = "# header\nid: demo # trailing\n\n  # indented comment\nurl: http://x/#frag\n"
    data = parse(text)
    assert data == {"id": "demo", "url": "http://x/#frag"}


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("  - orphan\n", "indented line without a block list key"),
        ("a: 1\na: 2\n", "duplicate key"),
        ("just words\n", "expected 'key: value'"),
        ("items:\n  - ok\n  not a list entry\n", "expected a '- item'"),
        ("value: [a, b\n", "must end with ']'"),
        ("value: \"open\n", "unterminated quoted value"),
        ("value: &anchor x\n", "unsupported YAML syntax"),
        ("value: |\n", "unsupported YAML syntax"),
        ("items:\n\t- tab\n", "tabs are not allowed"),
    ],
)
def test_outside_the_subset_raises_with_line(text, fragment):
    with pytest.raises(MiniYamlError, match=fragment):
        parse(text)
