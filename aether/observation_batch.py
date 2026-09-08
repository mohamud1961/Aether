"""Solver decision-frontier mutation generation token.

The historical certified read-only observation-batch executor was removed as
unreachable dead wiring: no production dispatch path or model surface can emit
an ``observe_batch`` action, so its receipt kind could never occur.  The
mutation-generation token remains load-bearing for Solver freshness checks.
"""
from __future__ import annotations

import hashlib

from .ledger import ExecutionLedger


def mutation_generation(ledger: ExecutionLedger) -> str:
    """Return a stable token for the currently observed mutation frontier."""
    mutations = [
        receipt for receipt in ledger.all_receipts()
        if receipt.state_change or ledger.is_uncertain_task_state_boundary(receipt)
    ]
    last = mutations[-1].receipt_id if mutations else "initial"
    material = f"{len(mutations)}\x00{last}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:20]
