from __future__ import annotations

from typing import List, Dict


def mandatory_verifier_phase_required(
    *,
    files_written_count: int,
    completion_signals: List[Dict[str, object]],
    verifier_run: bool,
) -> bool:
    if verifier_run:
        return False
    if files_written_count <= 0:
        return False
    return bool(completion_signals)
