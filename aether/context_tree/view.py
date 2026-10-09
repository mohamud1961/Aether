"""Append-only, most-due-pair history view [OptChat §5]."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TreeLookup(Protocol):
    @property
    def event_count(self) -> int: ...
    def get_node(self, level: int, index: int): ...


@dataclass(frozen=True)
class ViewPart:
    level: int
    index: int

    @property
    def span(self) -> int:
        return 1 << self.level

    @property
    def start(self) -> int:
        return self.index * self.span

    @property
    def end(self) -> int:
        return self.start + self.span

    @property
    def identifier(self) -> str:
        return f"{self.start}+{self.span}"


class UnsettledViewError(RuntimeError):
    """A solver request was attempted while a view summary was missing."""


class TreeView:
    def __init__(self, tree: TreeLookup, *, budget: int = 128_000) -> None:
        if budget < 1:
            raise ValueError("view budget must be positive")
        self.tree = tree
        self.budget = int(budget)
        self.parts: list[ViewPart] = []

    def append(self, event_index: int) -> None:
        covered = sum(part.span for part in self.parts)
        if event_index != covered:
            raise ValueError("view events must be appended in order")
        self.parts.append(ViewPart(0, event_index))
        self.fit()

    def is_built(self, part: ViewPart) -> bool:
        return self.tree.get_node(part.level, part.index) is not None

    def line_text(self, part: ViewPart) -> str:
        node = self.tree.get_node(part.level, part.index)
        return node.text if node is not None else "(not summarized yet: zoom it)"

    @property
    def size_bytes(self) -> int:
        return len(self.render(require_settled=False).encode("utf-8"))

    @property
    def settled(self) -> bool:
        return all(self.is_built(part) for part in self.parts)

    def fit(self) -> None:
        total = self.tree.event_count
        while self.size_bytes > self.budget:
            best_index: int | None = None
            best_due: float | None = None
            for index in range(len(self.parts) - 1):
                left, right = self.parts[index:index + 2]
                if left.level != right.level or left.index % 2 != 0 or right.index != left.index + 1:
                    continue
                if self.tree.get_node(left.level + 1, left.index // 2) is None:
                    continue
                start = left.start
                due = (total - start) / float(1 << (left.level + 2))
                if best_due is None or due > best_due:
                    best_index, best_due = index, due
            if best_index is None:
                break
            left = self.parts[best_index]
            self.parts[best_index:best_index + 2] = [
                ViewPart(left.level + 1, left.index // 2)
            ]

    def render(self, *, require_settled: bool = True) -> str:
        if require_settled and not self.settled:
            raise UnsettledViewError("view has an unbuilt summary")
        rows = []
        for part in self.parts:
            text = self.line_text(part).replace("\n", " ")
            rows.append(f"{part.identifier}|{text}")
        return "<chat>\n" + "\n".join(rows) + "\n</chat>"

    def common_prefix_bytes(self, other: "TreeView") -> int:
        left = self.render().encode("utf-8")
        right = other.render().encode("utf-8")
        i = 0
        while i < min(len(left), len(right)) and left[i] == right[i]:
            i += 1
        return i
