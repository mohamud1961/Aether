"""Task-local summary-tree context, adapted from the pinned OptChat design."""

from .config import CONTROL, M_TREE_V1, ContextModeError, resolve_context_mode
from .adapter import ContextTreeAdapter, ContextTreeContinuityError
from .epoch import EpochPolicy, MTreeEpochOverflow
from .store import RunStore
from .tree import ContextTree, NodeAddress, covers, node_identifier
from .zoom_tool import zoom

__all__ = [
    "CONTROL", "M_TREE_V1", "ContextModeError", "resolve_context_mode",
    "ContextTreeAdapter", "ContextTreeContinuityError", "EpochPolicy",
    "MTreeEpochOverflow", "RunStore", "ContextTree",
    "NodeAddress", "covers", "node_identifier", "zoom",
]
