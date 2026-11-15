"""Decide whether a price change is worth a notification."""

from __future__ import annotations

from decimal import Decimal


def should_notify(
    *,
    notified_before: bool,
    last_notified_price: Decimal | None,
    current_price: Decimal | None,
    min_change_abs: Decimal,
    min_change_pct: Decimal,
) -> bool:
    """Compare against the last *notified* price, so slow drifts add up and eventually notify.

    A price of None means no fare was found for at least one leg; switching between
    "fare" and "no fare" always notifies.
    """
    if not notified_before:
        return True
    if (last_notified_price is None) != (current_price is None):
        return True
    if current_price is None or last_notified_price is None:
        return False
    change = abs(current_price - last_notified_price)
    return change >= min_change_abs or change >= last_notified_price * min_change_pct / 100
