"""Source-faithful immutable task clauses for the direct PERSISTENT runtime.

PERSISTENT has no Architect model to compile task semantics. The raw visible task is
always authoritative. This module performs only mechanical presentation
factoring: it preserves the raw prompt byte-for-byte and exposes bounded units
of that same visible text as independent clause identities for completion and
Verifier coverage. It contains no benchmark knowledge and makes no semantic
judgment about hidden requirements.
"""
from __future__ import annotations

from hashlib import sha256
import re

from .task_contract import TaskClause, TaskContract


_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|[A-Za-z][.)]\s+)")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`/])")
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")
_APP_PATH_RE = re.compile(r"(?<![\w.-])(/app(?:/[\w.@+~:/-]+)+)")
_FILE_TOKEN_RE = re.compile(
    r"(?<![\w/.-])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.@+~-]+)*\.(?:"
    r"py|js|ts|sh|proto|toml|yaml|yml|json|jsonl|csv|txt|log|html|css|pem|crt|key|"
    r"mp4|mov|avi|mkv|png|jpg|jpeg|pdf|gcode|sql|sparql|bin|ftz|zip|7z"
    r"))(?![\w.-])",
    re.IGNORECASE,
)
_PORT_RE = re.compile(r"(?:\bport\s+|(?<!\d):)(\d{2,5})\b", re.IGNORECASE)
_VERSION_RE = re.compile(r"(?<!\d)(v?\d+\.\d+(?:\.\d+){0,2})(?!\d)", re.IGNORECASE)
_NAMED_IDENTIFIER_RE = re.compile(
    r"\b(?:field|method|function|class|key|property|service|message|header|column)\s+"
    r"(?:named\s+|called\s+)[`'\"]?([A-Za-z_][A-Za-z0-9_.-]*)[`'\"]?",
    re.IGNORECASE,
)
_DIRECT_IDENTIFIER_RE = re.compile(
    r"\b(?:field|method|function|class|key|property|service|message|header|column)\s+"
    r"[`'\"]?([A-Za-z_][A-Za-z0-9_.-]*)[`'\"]?",
    re.IGNORECASE,
)
_REVERSE_DATA_IDENTIFIER_RE = re.compile(
    r"\b[`'\"]?([A-Za-z_][A-Za-z0-9_.-]*)[`'\"]?\s+"
    r"(?=field\b|key\b|property\b|header\b|column\b)",
    re.IGNORECASE,
)
_PROTO_FIELD_RE = re.compile(
    r"\b(string|int32|int64|sint32|sint64|uint32|uint64|bool|bytes|float|double)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*=",
    re.IGNORECASE,
)
_ASSIGNMENT_KEY_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])([A-Za-z_][A-Za-z0-9_.-]{2,})\s*(?:=|:)\s*(?:[<[{'\"]|[A-Za-z0-9_-])"
)
_IDENTIFIER_STOPWORDS = frozenset({
    "a", "an", "the", "must", "should", "shall", "is", "are", "be", "named",
    "called", "with", "without", "for", "of", "to", "from", "that", "which",
    "containing", "contains", "include", "includes", "using", "exact", "required",
    "field", "method", "function", "class", "key", "property", "service",
    "message", "header", "column",
})
_REVERSE_IDENTIFIER_STOPWORDS = frozenset(
    (_IDENTIFIER_STOPWORDS - {"field", "key", "property", "header", "column"})
    | {"string", "int32", "int64", "sint32", "sint64", "uint32", "uint64", "bool", "bytes", "float", "double"}
)
_MAX_CLAUSES = 96
_MAX_ATOMS_PER_CLAUSE = 24
_MAX_HEADING_CHARS = 120


def compile_persistent_task_contract(raw_task_prompt: str) -> TaskContract:
    """Factor visible PERSISTENT task text into source-faithful completion clauses.

    This is not a semantic parser. The raw prompt remains verbatim authority;
    clauses contain only visible source wording (apart from bullet-prefix and
    whitespace normalisation), and exact atoms are best-effort navigation
    indexes. No generated paraphrase becomes task truth.

    A mechanically single-unit task retains the historical ``task:raw`` ID so
    source factoring does not churn the protocol for simple tasks. Multi-unit
    tasks receive stable source-derived IDs so independent visible requirements
    can be covered separately by the PERSISTENT completion bridge.
    """
    prompt = str(raw_task_prompt or "")
    if not prompt.strip():
        raise ValueError("raw_task_prompt must be non-empty")
    units = _visible_requirement_units(prompt)
    if len(units) == 1:
        clauses = (TaskClause("task:raw", units[0], _exact_atoms(units[0])),)
    else:
        clauses = tuple(
            TaskClause(
                clause_id=_clause_id(index, text),
                text=text,
                exact_atoms=_exact_atoms(text),
            )
            for index, text in enumerate(units, start=1)
        )
    if not clauses:
        clauses = (TaskClause("task:raw", prompt.strip(), _exact_atoms(prompt)),)
    return TaskContract.create(
        prompt,
        clauses,
        schema_version="persistent_v0_source_faithful",
    )




def source_linked_task_clauses(raw_task_prompt: str) -> tuple[dict[str, object], ...]:
    """Return exact visible source blocks with reversible raw-task locations.

    This is presentation-only factoring for M4. Every clause text is an exact
    substring of the raw prompt; no paraphrase, whitespace normalization, or
    semantic classification is performed. Character and UTF-8 byte spans are
    half-open indexes into the exact raw prompt.
    """
    prompt = str(raw_task_prompt or "")
    if not prompt.strip():
        raise ValueError("raw_task_prompt must be non-empty")

    fence_marker = chr(96) * 3
    lines = prompt.splitlines(keepends=True)
    spans: list[tuple[int, int]] = []
    cursor = 0
    paragraph_start: int | None = None
    paragraph_end: int | None = None
    fence_start: int | None = None
    in_fence = False

    def trimmed_span(start: int, end: int) -> tuple[int, int] | None:
        segment = prompt[start:end]
        left = len(segment) - len(segment.lstrip())
        right_text = segment.rstrip()
        if not right_text.strip():
            return None
        return start + left, start + len(right_text)

    def flush_paragraph() -> None:
        nonlocal paragraph_start, paragraph_end
        if paragraph_start is None or paragraph_end is None:
            paragraph_start = paragraph_end = None
            return
        bounded = trimmed_span(paragraph_start, paragraph_end)
        paragraph_start = paragraph_end = None
        if bounded is None:
            return
        start, end = bounded
        text = prompt[start:end]
        if (
            "\n" not in text
            and len(text) <= _MAX_HEADING_CHARS
            and text.rstrip().endswith(":")
        ):
            return
        spans.append((start, end))

    for raw_line in lines:
        start = cursor
        end = cursor + len(raw_line)
        cursor = end
        stripped = raw_line.strip()

        if stripped.startswith(fence_marker):
            if in_fence:
                bounded = trimmed_span(fence_start or start, end)
                if bounded is not None:
                    spans.append(bounded)
                fence_start = None
                in_fence = False
            else:
                flush_paragraph()
                fence_start = start
                in_fence = True
            continue

        if in_fence:
            continue
        if not stripped:
            flush_paragraph()
            continue
        if _BULLET_PREFIX_RE.match(raw_line):
            flush_paragraph()
            bounded = trimmed_span(start, end)
            if bounded is not None:
                spans.append(bounded)
            continue
        if paragraph_start is None:
            paragraph_start = start
        paragraph_end = end

    if in_fence and fence_start is not None:
        bounded = trimmed_span(fence_start, len(prompt))
        if bounded is not None:
            spans.append(bounded)
    flush_paragraph()

    if not spans:
        bounded = trimmed_span(0, len(prompt))
        if bounded is not None:
            spans.append(bounded)

    if len(spans) > _MAX_CLAUSES:
        overflow_start = spans[_MAX_CLAUSES - 1][0]
        spans = spans[: _MAX_CLAUSES - 1] + [(overflow_start, spans[-1][1])]

    rows: list[dict[str, object]] = []
    for index, (start, end) in enumerate(spans, start=1):
        text = prompt[start:end]
        digest = sha256(text.encode("utf-8")).hexdigest()
        rows.append({
            "clause_id": f"source:{index:03d}:{digest[:10]}",
            "text": text,
            "source_char_start": start,
            "source_char_end": end,
            "source_byte_start": len(prompt[:start].encode("utf-8")),
            "source_byte_end": len(prompt[:end].encode("utf-8")),
            "source_sha256": digest,
        })
    return tuple(rows)


def raw_task_contract(raw_task_prompt: str) -> TaskContract:
    """Bind the exact task without deriving semantic clauses or atoms.

    The native PERSISTENT production path keeps a typed wrapper for custody and hashing,
    but deliberately does not turn bullets, examples, filenames, or prose into
    runtime obligations.  The raw prompt remains the only semantic authority;
    the single clause is an opaque transport binding only.
    """
    prompt = str(raw_task_prompt or "")
    if not prompt.strip():
        raise ValueError("raw_task_prompt must be non-empty")
    return TaskContract.create(
        prompt,
        (TaskClause("raw_task", prompt, ()),),
        schema_version="persistent_v11_raw",
    )


def _heading_only(parts: list[str]) -> bool:
    return (
        len(parts) == 1
        and len(parts[0]) <= _MAX_HEADING_CHARS
        and parts[0].rstrip().endswith(":")
    )


def _visible_requirement_units(prompt: str) -> tuple[str, ...]:
    """Return bounded units copied mechanically from visible task text."""
    units: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        if _heading_only(paragraph):
            paragraph.clear()
            return
        text = " ".join(part.strip() for part in paragraph if part.strip()).strip()
        paragraph.clear()
        if not text:
            return
        pieces = _SENTENCE_BOUNDARY_RE.split(text) if len(text) > 220 else [text]
        units.extend(piece.strip() for piece in pieces if piece.strip())

    in_fence = False
    fence_lines: list[str] = []
    for raw_line in prompt.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            if in_fence:
                fence_lines.append(line)
                block = "\n".join(fence_lines).strip()
                if block:
                    units.append(block)
                fence_lines.clear()
                in_fence = False
            else:
                flush_paragraph()
                in_fence = True
                fence_lines = [line]
            continue
        if in_fence:
            fence_lines.append(line)
            continue
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        if _BULLET_PREFIX_RE.match(line):
            flush_paragraph()
            item = _BULLET_PREFIX_RE.sub("", line, count=1).strip()
            if item:
                units.append(item)
            continue
        paragraph.append(stripped)
    if in_fence and fence_lines:
        units.append("\n".join(fence_lines).strip())
    flush_paragraph()

    deduped: list[str] = []
    seen: set[str] = set()
    for unit in units:
        normalized = unit.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    if len(deduped) <= _MAX_CLAUSES:
        return tuple(deduped)
    overflow = "\n".join(deduped[_MAX_CLAUSES - 1 :])
    return tuple(deduped[: _MAX_CLAUSES - 1] + [overflow])


def _clause_id(index: int, text: str) -> str:
    digest = sha256(text.encode("utf-8")).hexdigest()[:10]
    return f"task:{index:03d}:{digest}"


def _exact_atoms(text: str) -> tuple[str, ...]:
    atoms: list[str] = []

    def add(value: str) -> None:
        item = value.strip().strip(".,;:()[]{}")
        if item and item not in atoms and len(atoms) < _MAX_ATOMS_PER_CLAUSE:
            atoms.append(item)

    for regex in (_BACKTICK_RE, _APP_PATH_RE, _FILE_TOKEN_RE, _VERSION_RE, _NAMED_IDENTIFIER_RE):
        for match in regex.finditer(text):
            add(match.group(1))
    for match in _DIRECT_IDENTIFIER_RE.finditer(text):
        candidate = match.group(1)
        if candidate.lower() not in _IDENTIFIER_STOPWORDS:
            add(candidate)
    for match in _REVERSE_DATA_IDENTIFIER_RE.finditer(text):
        candidate = match.group(1)
        if candidate.lower() not in _REVERSE_IDENTIFIER_STOPWORDS:
            add(candidate)
    for match in _PROTO_FIELD_RE.finditer(text):
        add(match.group(1))
        add(match.group(2))
    for match in _ASSIGNMENT_KEY_RE.finditer(text):
        candidate = match.group(1)
        if candidate.lower() not in _IDENTIFIER_STOPWORDS:
            add(candidate)
    for match in _PORT_RE.finditer(text):
        add(match.group(1))
    return tuple(atoms)
