"""Generic structural independence and self-consistency checks for verifier methods."""
from __future__ import annotations

import ast
import re
from typing import Iterable

_TOKEN_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|==|!=|<=|>=|//|<<|>>|[-+*/%<>{}()[\].,:]"
)
_HEREDOC_RE = re.compile(
    r"(?:^|[;&|]\s*|\n\s*)python(?:\d+(?:\.\d+)*)?\s+-\s*<<\s*['\"]?"
    r"([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*\n(.*?)\n\1(?:\s|$)",
    re.DOTALL,
)
_INTERPRETER_RE = r"(?:python(?:\d+(?:\.\d+)*)?|bash|sh|node|ruby|perl|php|lua|pwsh|powershell)"


def _token_shingles(text: str, *, width: int = 6) -> set[tuple[str, ...]]:
    tokens = [token.lower() for token in _TOKEN_RE.findall(str(text or ""))]
    if len(tokens) < width:
        return set()
    return {tuple(tokens[index:index + width]) for index in range(len(tokens) - width + 1)}


def same_method_overlap(
    command: str,
    observed_source_texts: Iterable[str],
    *,
    minimum_shared_shingles: int = 40,
    minimum_containment: float = 0.20,
) -> tuple[bool, dict[str, float | int]]:
    """Detect substantial literal method reuse without understanding the task."""
    command_shingles = _token_shingles(command)
    source_shingles: set[tuple[str, ...]] = set()
    for text in observed_source_texts:
        source_shingles |= _token_shingles(text)
    shared = command_shingles & source_shingles
    denominator = max(1, min(len(command_shingles), len(source_shingles)))
    containment = len(shared) / denominator
    details: dict[str, float | int] = {
        "command_shingles": len(command_shingles),
        "source_shingles": len(source_shingles),
        "shared_shingles": len(shared),
        "containment": round(containment, 4),
    }
    return (
        len(shared) >= minimum_shared_shingles
        and containment >= minimum_containment
    ), details


def executed_observed_implementations(command: str, observed_paths: Iterable[str]) -> tuple[str, ...]:
    """Return inspected paths that the proposed method directly executes.

    Under an explicit same-method risk, rerunning an inspected implementation
    and reading its output is useful exploratory evidence, but it is not an
    independent derivation.  This check is path/protocol based and does not
    infer task semantics.
    """
    reused: list[str] = []
    for raw_path in observed_paths:
        path = str(raw_path or "").strip()
        if not path:
            continue
        candidates = {path}
        if path.startswith("/app/"):
            candidates.add(path.removeprefix("/app/"))
            candidates.add("./" + path.removeprefix("/app/"))
        for candidate in candidates:
            escaped = re.escape(candidate)
            interpreted = re.compile(
                rf"(?:^|[;&|]\s*|\n\s*){_INTERPRETER_RE}\s+(?:-[^\s]+\s+)*['\"]?{escaped}['\"]?(?:\s|$)",
                re.IGNORECASE,
            )
            direct = re.compile(
                rf"(?:^|[;&|]\s*|\n\s*)['\"]?{escaped}['\"]?(?:\s|$)",
                re.IGNORECASE,
            )
            if interpreted.search(command) or direct.search(command):
                reused.append(path)
                break
    return tuple(dict.fromkeys(reused))


def _python_fragments(command: str) -> tuple[str, ...]:
    return tuple(match.group(2) for match in _HEREDOC_RE.finditer(str(command or "")))


def _literal_mapping_keys(tree: ast.AST) -> dict[str, set[object]]:
    mappings: dict[str, set[object]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if not isinstance(value, ast.Dict):
            continue
        keys = {
            key.value
            for key in value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, (str, int, float))
        }
        for target in targets:
            if isinstance(target, ast.Name) and keys:
                mappings[target.id] = keys
    return mappings


def _subscript_chain(node: ast.AST) -> tuple[str, tuple[tuple[str, object], ...]] | None:
    indexes: list[tuple[str, object]] = []
    current = node
    while isinstance(current, ast.Subscript):
        index = current.slice
        if isinstance(index, ast.Name):
            indexes.append(("name", index.id))
        elif isinstance(index, ast.Constant):
            indexes.append(("const", index.value))
        else:
            indexes.append(("expr", ast.dump(index, include_attributes=False)))
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    indexes.reverse()
    return current.id, tuple(indexes)


def _is_descendant(node: ast.AST, ancestor: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    current = parents.get(node)
    while current is not None:
        if current is ancestor:
            return True
        current = parents.get(current)
    return False


def _loop_collection(loop: ast.For) -> tuple[str, str] | None:
    collection = ""
    if isinstance(loop.iter, ast.Name):
        collection = loop.iter.id
    elif (
        isinstance(loop.iter, ast.Call)
        and isinstance(loop.iter.func, ast.Attribute)
        and isinstance(loop.iter.func.value, ast.Name)
        and loop.iter.func.attr in {"items", "keys"}
    ):
        collection = loop.iter.func.value.id
    if not collection:
        return None
    target = loop.target
    if isinstance(target, ast.Name):
        return collection, target.id
    if isinstance(target, (ast.Tuple, ast.List)) and target.elts and isinstance(target.elts[0], ast.Name):
        return collection, target.elts[0].id
    return None


def overlapping_accumulator_problem(command: str) -> str:
    """Detect a verifier script that can count the same bucket twice.

    The mechanical pattern is generic: a literal mapping contains a named
    bucket, that bucket is updated explicitly, and the same accumulator is
    also updated through iteration over the full mapping.  The kernel does not
    decide the correct count; it refuses an internally overlapping method.
    """
    for fragment in _python_fragments(command):
        try:
            tree = ast.parse(fragment)
        except SyntaxError:
            continue
        mappings = _literal_mapping_keys(tree)
        if not mappings:
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        augments = [node for node in ast.walk(tree) if isinstance(node, ast.AugAssign)]
        for loop in (node for node in ast.walk(tree) if isinstance(node, ast.For)):
            collection_info = _loop_collection(loop)
            if collection_info is None:
                continue
            collection, key_name = collection_info
            literal_keys = mappings.get(collection, set())
            if not literal_keys:
                continue
            inside = [node for node in augments if _is_descendant(node, loop, parents)]
            outside = [node for node in augments if not _is_descendant(node, loop, parents)]
            for loop_update in inside:
                loop_chain = _subscript_chain(loop_update.target)
                if loop_chain is None:
                    continue
                base, loop_indexes = loop_chain
                key_positions = [i for i, item in enumerate(loop_indexes) if item == ("name", key_name)]
                for key_position in key_positions:
                    for direct_update in outside:
                        direct_chain = _subscript_chain(direct_update.target)
                        if direct_chain is None or direct_chain[0] != base:
                            continue
                        direct_indexes = direct_chain[1]
                        if len(direct_indexes) != len(loop_indexes):
                            continue
                        literal = direct_indexes[key_position]
                        if literal[0] != "const" or literal[1] not in literal_keys:
                            continue
                        if any(
                            loop_indexes[i] != direct_indexes[i]
                            for i in range(len(loop_indexes))
                            if i != key_position
                        ):
                            continue
                        return (
                            f"accumulator {base!r} updates bucket {literal[1]!r} directly and also through "
                            f"iteration over mapping {collection!r}, which contains that bucket"
                        )
    return ""
