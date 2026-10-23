"""Shared limit for individual change amounts, including extracted prices."""
import math

MAX_CHANGE_AMOUNT = 1_000_000_000


def usable_change_price(value):
    """Unusable extracted prices stay unpriced until a person supplies a valid amount."""
    try:
        amount = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return amount if math.isfinite(amount) and abs(amount) <= MAX_CHANGE_AMOUNT else None
