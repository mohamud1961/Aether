"""Money helpers for ledgerkit."""

from ledgerkit.config import SHARE_COUNT_LIMIT


def percent_of(cents: int, percent: int) -> int:
    """Return percent of cents, rounded half away from zero."""
    raw = cents * percent
    sign = -1 if raw < 0 else 1
    return sign * ((abs(raw) + 50) // 100)


def allocate(total_cents: int, weights: list[int]) -> list[int]:
    """Split total_cents across weights so the shares add up to total_cents exactly.

    Each share starts as the floor of its proportional amount. The leftover cents are then
    handed out one at a time, starting from the first share.
    """
    if not weights:
        raise ValueError("weights must not be empty")
    if len(weights) > SHARE_COUNT_LIMIT:
        raise ValueError(f"at most {SHARE_COUNT_LIMIT} shares")
    if any(w < 0 for w in weights):
        raise ValueError("weights must be non-negative")
    weight_sum = sum(weights)
    if weight_sum == 0:
        raise ValueError("weights must not all be zero")
    shares = [total_cents * w // weight_sum for w in weights]
    remainder = total_cents - sum(shares)
    for i in range(remainder - 1):
        shares[i] += 1
    return shares
