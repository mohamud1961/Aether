"""Byte transfer into the task environment: model-requested file writes (stage, commit, readback) and Core's own
control files, plus reads back out. Split from env.py, which keeps the environment protocol and process control."""

from __future__ import annotations

import base64
import hashlib
import os
import shlex
import tempfile
import uuid
from pathlib import Path

from .env import Environment, ExecResult, run

# Linux caps a single argv string at 128 KiB; stay well below it.
INLINE_BYTES = 48_000
# Exit codes of the staging script in put_bytes: each maps to the message its own step raised when every step was
# a separate exec (see docs/EXEC_COLLAPSE.md). The commit and readback scripts keep their own codes.
_RESOLVE, _DIRECTORY, _MKDIR, _PIN, _WRITE, _CHMOD = 10, 11, 16, 17, 13, 14


def _b64(data: bytes) -> str:
    return shlex.quote(base64.b64encode(data).decode())


def _sha256_of(path: str) -> str:
    """A command substitution expanding to the 64-hex SHA-256 of ``path`` (an already-quoted word). The space in
    ``$( (`` matters: ``$((`` would start arithmetic expansion."""
    return f"$( (sha256sum < {path} 2>/dev/null || shasum -a 256 < {path}) | cut -c1-64 )"


def _rename(src: str, dst: str) -> str:
    """A shell compound command that renames ``src`` over ``dst`` atomically, never moving a payload *inside* a
    directory. ``src`` and ``dst`` are already-quoted shell words."""
    replace = shlex.quote("import os,sys; os.replace(sys.argv[1],sys.argv[2])")
    return (
        f'if [ "$(uname -s)" = Linux ]; then mv -fT {src} {dst}; '
        f"else python3 -c {replace} {src} {dst}; fi"
    )


def atomic_write(path: str, data: bytes, code: int) -> str:
    """One shell statement that replaces a Core-owned control file with ``data``: temp file beside it, the staged
    bytes checked against the submitted digest, the same rename as :func:`put_bytes`, and the committed bytes read
    back. Any failure removes the temp file and exits ``code``. Only for paths under Core's control directory;
    model-requested paths go through :func:`put_bytes`, whose stage, commit and readback stay separate execs."""
    q = shlex.quote
    temporary = q(path + ".aether-" + uuid.uuid4().hex + ".tmp")
    digest = q(hashlib.sha256(data).hexdigest())
    return (
        f"{{ mkdir -p {q(os.path.dirname(path) or '.')} && "
        f"printf %s {_b64(data)} | base64 -d > {temporary} && "
        f'[ "{_sha256_of(temporary)}" = {digest} ] && {_rename(temporary, q(path))} && '
        f'[ "{_sha256_of(q(path))}" = {digest} ]; }} '
        f"|| {{ rm -f {temporary}; exit {code}; }}"
    )


def _stage_script(remote: str, suffix: str, payload: bytes | None, mode: str | None) -> str:
    """Resolve the target, refuse a directory, create and pin the physical parent, and (inline) stage the payload
    and its mode, in one exec. Prints the pinned target path. A failed or interrupted script removes its own stage.
    """
    q = shlex.quote
    stage = ""
    if payload is not None:
        stage = (
            f'tmp="$t"{q(suffix)}; printf %s {_b64(payload)} | base64 -d > "$tmp" || exit {_WRITE}; '
            + (f'chmod {q(mode)} "$tmp" || exit {_CHMOD}; ' if mode else "")
        )
    return (
        'tmp=""; trap \'[ -z "$tmp" ] || rm -f "$tmp" || echo "__AETHER_STAGE_LEFT__ $tmp" >&2\' 0; '
        # Command substitution drops trailing newlines; the "." keeps a path's own, the ${..%?} drops printf's.
        f"if [ -L {q(remote)} ]; then t=$({{ readlink -f {q(remote)} 2>/dev/null || realpath {q(remote)}; }} "
        f"&& printf .) || exit {_RESOLVE}; t=${{t%.}}; t=${{t%?}}; else t={q(remote)}; fi; "
        f"if [ -d \"$t\" ]; then echo 'write target is a directory' >&2; exit {_DIRECTORY}; fi; "
        # os.path.dirname / basename of the resolved target, in sh.
        'case "$t" in */*) p=${t%/*}; [ -n "$p" ] || p=/;; *) p=.;; esac; '
        f'mkdir -p "$p" || exit {_MKDIR}; '
        # Pin the physical parent once so later symlink pivots cannot strand staging or redirect this commit into a
        # different directory. This is pathname custody, not an atomic namespace/CAS guarantee.
        f'pp=$(cd "$p" && pwd -P && printf .) || exit {_PIN}; pp=${{pp%.}}; pp=${{pp%?}}; '
        't="${pp%/}/${t##*/}"; '
        + stage
        + "printf '%s\\n' \"$t\"; tmp=''"
    )


def _staging_error(result: ExecResult, remote: str) -> OSError:
    """The error the failed staging step raised when each step was its own exec."""
    detail = (result.stderr or result.stdout).strip()[:300]
    message = {
        _RESOLVE: f"cannot resolve write target {remote}",
        _DIRECTORY: f"cannot write {remote}: {detail}",
        _MKDIR: f"mkdir for {remote} failed: {result.stderr.strip()[:300]}",
        _PIN: f"physical parent for {remote} could not be established",
        _WRITE: f"write {remote} failed: {detail}",
        _CHMOD: f"preserving permissions of {remote} failed",
    }.get(result.code, f"write {remote} failed: {detail}")
    left = [line for line in result.stderr.splitlines() if line.startswith("__AETHER_STAGE_LEFT__ ")]
    if left:
        message += f"; staging cleanup unverified at {left[0].split(' ', 1)[1]}"
    return OSError(message)


async def put_bytes(
    env: Environment,
    data: bytes,
    remote: str,
    *,
    mode: str | None = None,
    expected_sha256: str | None = None,
) -> None:
    """Replace bytes atomically within the target directory. Interrupted transfers preserve the old file.

    Existing symlinks are followed; atomic replacement must not silently replace the link itself.

    Three environment calls for an inline payload, each a boundary a concurrent change can fall between: stage
    (resolve, refuse a directory, mkdir, pin the physical parent, write, chmod), commit (staged-bytes proof,
    destination type and optional expected-content checks, rename) and readback (requested-path identity and
    destination bytes). A larger payload adds the upload between stage and commit, where chmod then runs.
    """
    if expected_sha256 is not None and (
        len(expected_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in expected_sha256)
    ):
        raise ValueError("expected_sha256 must be a lowercase SHA-256 digest")
    q = shlex.quote
    inline = len(data) <= INLINE_BYTES
    suffix = ".aether-" + uuid.uuid4().hex + ".tmp"
    committed = staged_reported = False
    temporary: str | None = None
    try:
        staged = await run(
            env, _stage_script(remote, suffix, data if inline else None, mode if inline else None)
        )
        staged_reported = True  # from here the script's own trap has removed a failed stage, or reported it left
        if staged.code != 0 or not staged.stdout.endswith("\n"):
            raise _staging_error(staged, remote)
        target = staged.stdout.removesuffix("\n")
        temporary = target + suffix
        if not inline:
            with tempfile.TemporaryDirectory() as tmp:
                local = Path(tmp) / "payload"
                local.write_bytes(data)
                await env.upload_file(local, temporary)
        # Every stage, including inline base64 writes and exact text edits,
        # must have the bytes the model actually submitted before replacement.
        # Checking uploads but trusting smaller staged files made an otherwise
        # successful edit silently publish corrupt bytes after lower-layer
        # corruption. This check is part of the same remote commit command.
        expected_payload = hashlib.sha256(data).hexdigest()
        proof_label = "write integrity failure" if inline else "upload integrity failure"
        precondition = (
            f"chmod {q(mode)} {q(temporary)} || exit {_CHMOD}; " if mode and not inline else ""
        )
        precondition += (
            f"if [ ! -f {q(temporary)} ]; then "
            f"echo '{proof_label}: staged file missing' >&2; exit 12; fi; "
            f"actual_payload=$( (sha256sum < {q(temporary)} 2>/dev/null || "
            f"shasum -a 256 < {q(temporary)}) | cut -c1-64 ); "
            f'if [ "$actual_payload" != {q(expected_payload)} ]; then '
            f"echo '{proof_label}: staged bytes differ from submitted payload' >&2; exit 12; fi; "
        )
        precondition += (
            f"if [ -L {q(target)} ] || {{ [ -e {q(target)} ] && [ ! -f {q(target)} ]; }}; then "
            f"echo 'write conflict: destination changed to symlink or non-regular file before commit' >&2; exit 9; fi; "
        )
        if expected_sha256 is not None:
            # The comparison and final rename run in the SAME remote shell
            # invocation. This catches stale edits as late as practical,
            # though uncooperative concurrent writers can still race between
            # the hash check and rename: filesystem CAS is not guaranteed.
            precondition += (
                f"if [ ! -f {q(target)} ]; then echo 'edit conflict: source missing' >&2; exit 9; fi; "
                f"actual=$( (sha256sum < {q(target)} 2>/dev/null || "
                f"shasum -a 256 < {q(target)}) | cut -c1-64 ); "
                f'if [ "$actual" != {q(expected_sha256)} ]; then '
                f"echo 'edit conflict: file content changed before commit' >&2; exit 9; fi; "
                + (
                    f"current_mode=$(stat -Lc %a {q(target)} 2>/dev/null || "
                    f"stat -Lf %Lp {q(target)} 2>/dev/null); "
                    f'if [ "$current_mode" != {q(mode)} ]; then '
                    f"echo 'edit conflict: file permissions changed before commit' >&2; exit 9; fi; "
                    if mode
                    else ""
                )
            )
        # Rename the target pathname, never move a payload *inside* a directory.
        # Linux mv -T also rejects a directory that appeared after the preflight.
        # The non-Linux path supports local development with the same semantics.
        res = await run(env, precondition + _rename(q(temporary), q(target)))
        if res.code == _CHMOD and mode and not inline:
            raise OSError(f"preserving permissions of {remote} failed")
        if res.code != 0:
            raise OSError(
                f"committing write to {remote} failed: {res.stderr.strip()[:300]}"
            )
        committed = True
        # A successful rename acknowledges the operation, not the destination
        # bytes. Read the requested path again through the transport before
        # reporting success; it may have changed or a symlink may have pivoted.
        # This is an observation at acknowledgement time, never durable CAS.
        try:
            requested_parent = q(os.path.dirname(remote) or ".")
            readback = await run(
                env,
                # The identity runs in a subshell: its cd must not move the relative readback below.
                f"( if [ -L {q(remote)} ]; then readlink -f {q(remote)} 2>/dev/null || realpath {q(remote)}; "
                f"else cd {requested_parent} && actual_parent=$(pwd -P && printf .) && "
                "actual_parent=${actual_parent%.} && actual_parent=${actual_parent%?} && "
                f"printf '%s/%s\\n' \"${{actual_parent%/}}\" {q(os.path.basename(remote))}; fi ) "
                "|| echo __AETHER_NO_IDENTITY__; echo __AETHER_PROOF__; "
                f"if [ ! -f {q(remote)} ]; then echo 'destination is not a regular file' >&2; exit 13; fi; "
                f"sha256sum < {q(remote)} 2>/dev/null || shasum -a 256 < {q(remote)} 2>/dev/null",
            )
            identity, marker, proof = readback.stdout.rpartition("__AETHER_PROOF__\n")
            if (
                not marker
                or "__AETHER_NO_IDENTITY__" in identity
                or identity.removesuffix("\n") != target
            ):
                raise OSError("requested path changed after commit")
        except Exception as exc:
            raise OSError(
                f"write committed to {remote}, but destination could not be verified"
            ) from exc
        if readback.code != 0 or not proof.split():
            raise OSError(
                f"write committed to {remote}, but destination could not be verified"
            )
        if proof.split()[0] != expected_payload:
            raise OSError(
                f"write committed to {remote}, but destination bytes differ from submitted payload"
            )

    finally:
        if not committed and (temporary is not None or not staged_reported):
            import sys

            original = sys.exc_info()[1]
            try:
                if temporary is not None:
                    cleanup = await run(env, f"rm -f {q(temporary)}")
                else:
                    # The staging exec failed to report (transport error, cancellation): its own trap removes the
                    # stage when the script ends; re-resolve the same path to remove one it could not.
                    cleanup = await run(
                        env,
                        _stage_script(remote, suffix, None, None).replace(
                            "printf '%s\\n' \"$t\"; tmp=''", f'rm -f "$t"{q(suffix)}'
                        ),
                    )
                if cleanup.code != 0:
                    raise OSError(
                        cleanup.stderr[:200] or "stage removal did not report success"
                    )
            except Exception as cleanup_error:
                detail = f"staging cleanup unverified at {temporary or remote + suffix}: {cleanup_error}"
                if isinstance(original, Exception):
                    raise OSError(f"{original}; {detail}") from original
                if original is not None:
                    original.add_note(
                        detail
                    )  # preserve cancellation, with partial-effect evidence
                else:
                    raise OSError(detail) from cleanup_error


async def get_bytes(env: Environment, remote: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "payload"
        await env.download_file(remote, local)
        return local.read_bytes()
