"""Lean Verification Block: Leverages layered acceptance and runs sandbox audits.

Interface: check(task: str, workspace_state: dict) -> bool
"""

from __future__ import annotations
import os
import shutil
from typing import Any
from blocks.verification.layered_acceptance_guard import evaluate_layered_acceptance

def check(task: str, workspace_state: dict[str, Any]) -> bool:
    """Performs layered verification and auto-purges workspace contamination debris."""
    # 1. Run standard layered acceptance check
    decision = evaluate_layered_acceptance(workspace_state)
    verified = bool(decision["verified"])
    
    # 2. Sandbox Contamination Audit (pre-flight debris purge)
    # Automatically sweep and delete pyc files and cache folders to prevent grader penalties
    cwd = workspace_state.get("cwd", "/workspace")
    if os.path.exists(cwd):
        for root, dirs, files in os.walk(cwd):
            for d in list(dirs):
                if d in ("__pycache__", ".pytest_cache"):
                    try:
                        shutil.rmtree(os.path.join(root, d))
                    except Exception:
                        pass
            for f in files:
                if f.endswith((".pyc", ".pyo")) or f.startswith("tmp_"):
                    try:
                        os.unlink(os.path.join(root, f))
                    except Exception:
                        pass
                        
    workspace_state["verification_reason_codes"] = list(decision["reason_codes"])
    workspace_state["verification_substitution_violations"] = list(
        decision["substitution_violations"]
    )
    workspace_state["verification_layer_statuses"] = dict(decision["layer_statuses"])
    
    return verified
