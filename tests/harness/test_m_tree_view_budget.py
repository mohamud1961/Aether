from __future__ import annotations

from dataclasses import dataclass

from aether.context_tree.view import TreeView


@dataclass(frozen=True)
class Node:
    text: str


class TinyTree:
    def __init__(self, nodes):
        self.event_count = 0
        self.nodes = nodes

    def get_node(self, level, index):
        return self.nodes.get((level, index))


def test_view_budget_counts_serialized_overhead_when_folding():
    tree = TinyTree({
        (0, 0): Node("a"),
        (0, 1): Node("b"),
        (1, 0): Node("c"),
    })
    parent_render = "<chat>\n0+2|c\n</chat>"
    budget = len(parent_render.encode("utf-8"))
    unfolded_render = "<chat>\n0+1|a\n1+1|b\n</chat>"
    assert 2 <= budget < len(unfolded_render.encode("utf-8"))

    view = TreeView(tree, budget=budget)
    tree.event_count = 1
    view.append(0)
    tree.event_count = 2
    view.append(1)

    assert view.render() == parent_render
    assert view.size_bytes == budget
    assert [(part.level, part.index) for part in view.parts] == [(1, 0)]


def test_view_size_bytes_matches_rendered_utf8_length():
    tree = TinyTree({(0, 0): Node("café 🧪")})
    tree.event_count = 1
    view = TreeView(tree)
    view.append(0)

    rendered = view.render()
    assert view.size_bytes == len(rendered.encode("utf-8"))
    assert view.size_bytes > len(rendered)
