"""One price check for one trip: record changes, decide on a notification, update state."""

from __future__ import annotations

from datetime import datetime, timedelta

from ryanair_price_monitor import notify
from ryanair_price_monitor.decision import should_notify
from ryanair_price_monitor.prices import TripPrice
from ryanair_price_monitor.state import PriceStore

SUMMARY_WINDOW = timedelta(hours=24)


def daily_stats(store: PriceStore, trip_id: str, now: datetime, result: TripPrice) -> notify.DailyStats:
    history = store.price_history(trip_id, now - SUMMARY_WINDOW)
    prices = [p.total for p in history if p.total is not None]
    if result.total_decimal is not None:
        prices.append(result.total_decimal)
    return notify.DailyStats(
        min_price=min(prices, default=None),
        max_price=max(prices, default=None),
        changes=len(history),
    )


def check_trip(
    result: TripPrice,
    store: PriceStore,
    ntfy: notify.NtfyConfig,
    now: datetime,
    daily_summary: bool = False,
) -> dict:
    """Returns a log record describing what happened."""
    trip = result.trip
    trip_id = trip.trip_id
    state = store.get_state(trip_id)
    current = result.total_decimal
    now_iso = now.isoformat(timespec="seconds")

    changed = not state.checked_before or state.last_price != current
    if changed:
        store.record_price(trip_id, now, result)

    previous = (
        notify.Previous(price=state.last_notified_price, at=state.last_notified_at)
        if state.notified_before
        else None
    )

    if daily_summary:
        notify.send_summary(ntfy, result, previous, daily_stats(store, trip_id, now, result))
        action = "summary"
    elif should_notify(
        notified_before=state.notified_before,
        last_notified_price=state.last_notified_price,
        current_price=current,
        min_change_abs=trip.min_change_abs,
        min_change_pct=trip.min_change_pct,
    ):
        notify.send(ntfy, result, previous)
        action = "notified"
    else:
        action = "silent"

    state.last_price = current
    state.last_checked_at = now_iso
    if action != "silent":
        # The summary shows the price too, so later thresholds are measured from it.
        state.last_notified_price = current
        state.last_notified_at = now_iso
    store.save_state(trip_id, state)

    return {
        "trip_id": trip_id,
        "total": float(current) if current is not None else None,
        "currency": result.currency,
        "changed": changed,
        "action": action,
    }
