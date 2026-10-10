"""Kernel execution of the opt-in ``edit_file`` action.

A successful edit emits a receipt of kind ``write_file`` carrying the same
custody payload as a whole-file write (path, modified/artifact paths, before and
after hashes, full new content, file handle), so receipts, evidence, WorldState,
inspect_diff, completion guards, and every other write_file consumer see it as a
file write.  Only the model-visible ``excerpt`` differs: it is the short diff of
the changed region instead of the head/tail of the file.

A refused edit (no match, ambiguous match, missing file, ...) changes nothing and
emits an ``edit_file`` receipt with ``success=False``; it is deliberately not a
``write_file`` receipt, so no consumer mistakes it for a write.
"""
from __future__ import annotations

from hashlib import sha256

from .edit_file_tool import EDIT_FILE_ACTION, apply_edit
from .execution import Executor
from .ledger import Receipt
from .runtime_ir import ActionRequest, EnvMap, normalize_relpath


def execute_edit_file(
    action: ActionRequest, step: int, executor: Executor, envmap: EnvMap,
) -> list[Receipt]:
    path = normalize_relpath(str(action.arguments.get("path", "")), envmap.workspace_root)
    receipt_id = f"step-{step}:{action.action_id}:edit"

    def refused(failure_class: str, message: str) -> list[Receipt]:
        return [Receipt(
            receipt_id=receipt_id, step=step, kind=EDIT_FILE_ACTION, success=False,
            summary=f"edit_file refused for {path}: {message}", state_change=False,
            failure_class=failure_class,
            payload={"path": path, "detail": message, "file_handle": f"file:{path}"},
        )]

    if not executor.exists(path):
        return refused("edit_file_missing", "file does not exist; use write_file to create it")
    before = executor.read_file(path)
    result = apply_edit(before, action.arguments, path=path)
    if not result.ok:
        return refused(result.failure_class, result.message)

    executor.write_file(path, result.new_content)
    after_hash = sha256(result.new_content.encode("utf-8", "replace")).hexdigest()
    before_hash = sha256(before.encode("utf-8", "replace")).hexdigest()[:16]
    span = (
        f"line {result.first_line}" if result.first_line == result.last_line
        else f"lines {result.first_line}-{result.last_line}"
    )
    what = {
        "replace": "replaced 1 occurrence",
        "replace_all": f"replaced {result.replacements} occurrence(s)",
        "insert": "inserted text",
    }[result.form]
    payload = {
        "path": path,
        "modified_paths": (path,),
        "artifact_paths": (path,),
        "candidate_id": action.candidate_id,
        "before_content_hash": before_hash,
        "after_content_hash": after_hash,
        "content_sha256": after_hash,
        "content_sha256_provenance": "captured_bytes",
        "before_bytes": len(before),
        "bytes": len(result.new_content.encode("utf-8", "replace")),
        "chars": len(result.new_content),
        "content": result.new_content,
        "excerpt": result.diff,
        "file_handle": f"file:{path}",
        "edit_form": result.form,
        "edit_replacements": result.replacements,
        "edit_first_line": result.first_line,
        "edit_last_line": result.last_line,
    }
    return [Receipt(
        receipt_id=f"step-{step}:{action.action_id}:write", step=step,
        kind="write_file", success=True, state_change=True,
        summary=f"edited {path}: {what}, {span} of the new file",
        payload={k: v for k, v in payload.items() if v is not None and v != ""},
    )]
