"""File tools: line-numbered reads, whole-file writes and exact-match edits.

Writes keep an existing file's permission bits. Relative paths resolve against
the task working directory.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import difflib
import hashlib
import posixpath
import shlex

from .tool_validate import unsendable_text
from .env import Environment, get_bytes, put_bytes, run  # transfer names via env: a stdlib test stubs .env alone

MAX_READ_CHARS = 40_000
DEFAULT_LINES = 400


def _edit_miss_evidence(path: str, payload: bytes, text: str, old_str: str) -> str:
    """Where the intended text really is, from read-time bytes only: never an invented corrected edit.

    y12-y14: 34 of 456 edits missed and the next call was usually a full re-read. The message now leads with the
    file's own lines near the best anchor (numbered), and says when old_str matches apart from whitespace. The file
    may change after this read, so none of it is a durable current-version claim.
    """
    observed = hashlib.sha256(payload).hexdigest()
    label = f"observed read-time sha256={observed} (not a current/durable file guarantee)"
    lines = text.split("\n")
    want = [w.strip() for w in old_str.strip("\n").split("\n")]
    have = [h.strip() for h in lines]
    if want and any(want):
        for i in range(len(have) - len(want) + 1):
            if have[i : i + len(want)] == want:
                return (f"old_str matches lines {i + 1}-{i + len(want)} apart from whitespace or indentation; "
                        f"copy their exact text:\n{_numbered(lines, i, i + len(want))}\n({label})")
    anchors = [part[:96] for part in old_str[:2048].split() if len(part) >= 8]
    anchors = sorted(anchors[:12], key=len, reverse=True)[:4]
    for anchor in anchors:
        index = text.find(anchor)
        if index < 0:
            continue
        line = text.count("\n", 0, index)
        return (f"the file's own lines near an exact fragment of old_str (line {line + 1}):\n"
                f"{_numbered(lines, max(0, line - 3), min(len(lines), line + len(want) + 3))}\n({label})")
    first = next((w for w in want if w), "")
    close = difflib.get_close_matches(first, have, n=1, cutoff=0.6) if first and len(lines) <= 20_000 else []
    if close:
        line = have.index(close[0])
        return (f"no exact fragment of old_str was found; the file's line most like its first line is {line + 1}:\n"
                f"{_numbered(lines, max(0, line - 3), min(len(lines), line + len(want) + 3))}\n({label})")
    return f"no fragment of old_str was found in the file; re-read it ({label})"


def _numbered(lines: list[str], begin: int, end: int, cap: int = 40, width: int = 240) -> str:
    end = min(end, begin + cap)
    return "\n".join(f"{n + 1:6d}  {lines[n][:width]}{'…' if len(lines[n]) > width else ''}" for n in range(begin, end))


class Files:
    def __init__(self, env: Environment, workdir: str) -> None:
        self._env = env
        self._workdir = workdir
        self.written: dict[
            str, int
        ] = {}  # path -> bytes, for the record and the reviewer

    def resolve(self, path: str) -> str:
        path = str(path)
        if not path:
            raise ValueError("path is empty")
        return posixpath.normpath(
            path if path.startswith("/") else posixpath.join(self._workdir, path)
        )

    async def _mode(self, path: str) -> str | None:
        q = shlex.quote(path)
        res = await run(
            self._env,
            f"if [ -e {q} ] || [ -L {q} ]; then "
            f"if [ -d {q} ]; then echo 'write target is a directory' >&2; exit 4; fi; "
            f"if [ ! -f {q} ]; then echo 'write target is not a regular file' >&2; exit 5; fi; "
            f"stat -Lc %a {q} 2>/dev/null || stat -Lf %Lp {q}; else echo MISSING; fi",
        )
        if res.code == 4:
            raise OSError(f"write target is a directory: {path}")
        if res.code == 5:
            raise OSError(f"write target is not a regular file: {path}")
        mode = res.stdout.strip()
        if res.code != 0 or (mode != "MISSING" and not mode.isdigit()):
            raise OSError(f"cannot determine permissions of {path}")
        return None if mode == "MISSING" else mode

    async def read(
        self,
        path: str,
        start_line: int = 1,
        num_lines: int = DEFAULT_LINES,
        offset: int = 0,
    ) -> str:
        path = self.resolve(path)
        if offset < 0:
            raise ValueError("offset must be non-negative")
        start = max(1, int(start_line))
        end = start + max(1, min(int(num_lines), 4000)) - 1
        q = shlex.quote(path)
        # Slice numbered UTF-8 output in bytes, bounding remote staging to one
        # page even if selected source lines are huge. The decoder below owns
        # incomplete trailing code points and the continuation byte offset.
        page_program = (
            f"BEGIN {{skip={offset}; left={MAX_READ_CHARS + 1}}} "
            # Only the number goes through sprintf: mawk (the Debian/Ubuntu default awk) caps a sprintf result at
            # 8192 bytes, so formatting the whole line failed every read of a file with a longer line.
            f'NR>={start} && NR<={end} {{line=sprintf("%6d  ",NR) $0 "\\n"; n=length(line); '
            "if(skip>=n) {skip-=n} else {line=substr(line,skip+1); skip=0; "
            'if(length(line)>left) line=substr(line,1,left); printf "%s",line; '
            "left-=length(line); if(left==0) exit}} "
            f"NR>{end} {{exit}}"
        )
        res = await run(
            self._env,
            f"if [ ! -f {q} ]; then echo 'not a regular file (or missing)' >&2; exit 2; fi; "
            f"if [ ! -r {q} ]; then echo 'file is not readable' >&2; exit 3; fi; "
            f"if [ -s {q} ]; then grep -qI '' {q}; kind=$?; "
            f"if [ $kind -gt 1 ]; then echo 'file classification read failed' >&2; exit 3; fi; "
            f"if [ $kind -eq 1 ]; then echo BINARY; wc -c < {q} || exit 3; exit 0; fi; fi; "
            f"total=$(awk 'END {{print NR}}' {q}) || exit 3; "
            "read_tmp=$(mktemp -d) || exit 3; "
            "trap 'rm -rf \"$read_tmp\"' 0; "
            f'LC_ALL=C awk {shlex.quote(page_program)} {q} > "$read_tmp/page" || exit 3; '
            'page_hash=$( (sha256sum < "$read_tmp/page" 2>/dev/null || '
            'shasum -a 256 < "$read_tmp/page" 2>/dev/null) | cut -c1-64); '
            "if [ ${#page_hash} -ne 64 ]; then echo 'read integrity hash unavailable' >&2; exit 3; fi; "
            "case \"$page_hash\" in *[!0-9a-f]*) echo 'read integrity hash invalid' >&2; exit 3;; esac; "
            'printf \'%s\\n%s\\n\' "$total" "$page_hash"; '
            'base64 < "$read_tmp/page" || exit 3',
        )
        if res.code == 3:
            raise OSError(
                f"cannot read {path}: {(res.stderr or res.stdout).strip()[:200]}"
            )

        if res.code != 0:
            raise FileNotFoundError(
                f"{path}: {(res.stderr or res.stdout).strip()[:200]}"
            )
        if res.stdout.startswith("BINARY\n"):
            size = res.stdout.split()[1] if len(res.stdout.split()) > 1 else "?"
            return (
                f"[{path}: binary file, {size} bytes; not shown as text. Inspect it in the terminal "
                f"(xxd, od, file, strings) or with the python tool]"
            )
        total_s, _, remainder = res.stdout.partition("\n")
        digest_s, _, body = remainder.partition("\n")
        if (
            not total_s.isdigit()
            or len(digest_s) != 64
            or any(ch not in "0123456789abcdef" for ch in digest_s)
        ):
            raise OSError(
                f"cannot verify read response for {path}: missing page identity"
            )
        total = int(total_s)
        try:
            encoded = "".join(body.split())
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise OSError(
                f"cannot verify read response for {path}: malformed base64 page"
            ) from exc
        if hashlib.sha256(payload).hexdigest() != digest_s:
            raise OSError(
                f"cannot verify read response for {path}: page bytes differ from source observation"
            )
        more_bytes = len(payload) > MAX_READ_CHARS
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        body = decoder.decode(payload[:MAX_READ_CHARS], final=not more_bytes)
        consumed = min(len(payload), MAX_READ_CHARS) - len(decoder.getstate()[0])
        shown_end = min(end, total)
        if more_bytes:
            more = f"; same line selection: next_offset={offset + consumed}"
        else:
            more = f"; next: start_line={shown_end + 1}" if shown_end < total else ""
        return f"{body.rstrip(chr(10))}\n[{path}: lines {start}-{shown_end} of {total}{more}]"

    async def write(self, path: str, content: str) -> str:
        reason = unsendable_text(content, shell=False)
        if reason:
            raise ValueError(f"{path}: not written, nothing ran: {reason}")
        path = self.resolve(path)
        mode = await self._mode(path)
        data = content.encode()
        await put_bytes(self._env, data, path, mode=mode)
        self.written[path] = len(data)
        lines = content.count("\n") + (
            0 if content.endswith("\n") or not content else 1
        )
        return f"wrote {len(data)} bytes ({lines} lines) to {path}" + (
            "" if mode else " (new file)"
        )

    async def edit(
        self, path: str, old_str: str, new_str: str, replace_all: bool = False
    ) -> str:
        path = self.resolve(path)
        if not old_str:
            raise ValueError(
                "old_str is empty; use write_file to create or replace a whole file"
            )
        # Check the file type before download_file opens the path: reading a FIFO
        # can otherwise wait indefinitely for a writer before the edit can fail.
        mode = await self._mode(path)
        payload = await get_bytes(self._env, path)
        try:
            text = payload.decode()
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path} is not UTF-8 text") from exc
        count = text.count(old_str)
        if count == 0:
            evidence = _edit_miss_evidence(path, payload, text, old_str)
            raise ValueError(
                f"old_str not found in {path}; no write attempted; {evidence}"
            )
        if count > 1 and not replace_all:
            raise ValueError(
                f"old_str occurs {count} times in {path}; add context to make it unique "
                f"or set replace_all=true"
            )
        # The first actual edit starts at the first old_str in the *source*.
        # Looking for new_str in updated text is wrong if that same new_str
        # already occurred earlier: the receipt then points at an unchanged
        # line and can mislead the model about which source bytes it edited.
        first_edit_at = text.find(old_str)
        updated = (
            text.replace(old_str, new_str)
            if replace_all
            else text.replace(old_str, new_str, 1)
        )
        # Exact edit only: do not silently replace source bytes that changed
        # after the one raw read used to locate the model's old_str.
        # The substrate rechecks this hash immediately before rename, though
        # an uncooperative writer can still race that check (not atomic CAS).
        await put_bytes(
            self._env,
            updated.encode(),
            path,
            mode=mode,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )
        self.written[path] = len(updated.encode())
        line = text.count("\n", 0, first_edit_at) + 1
        lines = updated.split("\n")
        lo, hi = max(0, line - 4), min(len(lines), line + new_str.count("\n") + 3)
        snippet = "\n".join(f"{i + 1:6d}  {lines[i]}" for i in range(lo, hi))
        return f"edited {path} ({count if replace_all else 1} replacement{'s' if replace_all and count > 1 else ''})\n{snippet}"
