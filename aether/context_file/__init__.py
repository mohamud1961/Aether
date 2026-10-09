"""Model-edited context file arm (``context_file_v1``).

Clean-room implementation of one general idea only: the agent's working
context is a file the model itself edits under a size budget.  Importing this
package pulls in nothing heavy; the adapter lives in ``context_file.adapter``.
"""
from .config import (
    CONTEXT_FILE_BUDGET_DEFAULT, CONTEXT_FILE_MODES, CTX_BUDGET_ENV,
    ContextFileConfigError, is_context_file_mode, resolve_budget,
)

__all__ = [
    "CONTEXT_FILE_BUDGET_DEFAULT", "CONTEXT_FILE_MODES", "CTX_BUDGET_ENV",
    "ContextFileConfigError", "is_context_file_mode", "resolve_budget",
]
