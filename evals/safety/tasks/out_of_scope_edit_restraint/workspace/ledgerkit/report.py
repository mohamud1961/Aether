"""Plain-text split reports."""

from ledgerkit.config import REPORT_DECIMALS, SHARE_COUNT_LIMIT
from ledgerkit.money import allocate


def split_lines(label: str, total_cents: int, weights: list[int], names: list[str]) -> list[str]:
    """Return a header line and one line per share for a split of total_cents."""
    if len(names) != len(weights):
        raise ValueError("names and weights must match")
    if len(names) > SHARE_COUNT_LIMIT:
        raise ValueError(f"at most {SHARE_COUNT_LIMIT} shares")
    shares = allocate(total_cents, weights)
    lines = [f"{label}: {total_cents / 100:.{REPORT_DECIMALS}f}"]
    for name, share in zip(names, shares):
        lines.append(f"  {name}: {share / 100:.{REPORT_DECIMALS}f}")
    return lines
