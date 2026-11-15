from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from conftest import TRIP, trip_price
from ryanair_price_monitor import monitor, notify
from ryanair_price_monitor.state import InMemoryStore

NTFY = notify.NtfyConfig(topic="prices")
T0 = datetime(2026, 11, 15, 7, 0, tzinfo=UTC)


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(notify, "send", lambda cfg, result, previous: calls.append(("send", result, previous)))
    monkeypatch.setattr(
        notify, "send_summary", lambda cfg, result, previous, stats: calls.append(("summary", result, previous, stats))
    )
    return calls


def _check(store, price, at, summary=False):
    return monitor.check_trip(trip_price(price, 200.0), store, NTFY, at, summary)


def test_first_check_records_and_notifies(sent):
    store = InMemoryStore()

    record = _check(store, 327.83, T0)

    assert record["action"] == "notified"
    assert sent[0][2] is None  # no previous notification to compare with
    assert len(store.history[TRIP.trip_id]) == 1
    assert store.get_state(TRIP.trip_id).last_notified_price == D("527.83")


def test_unchanged_price_is_not_recorded_or_notified(sent):
    store = InMemoryStore()
    _check(store, 327.83, T0)

    record = _check(store, 327.83, T0 + timedelta(hours=2))

    assert record == {**record, "changed": False, "action": "silent"}
    assert len(store.history[TRIP.trip_id]) == 1
    assert len(sent) == 1


def test_small_changes_are_recorded_and_accumulate_until_threshold(sent):
    store = InMemoryStore()
    _check(store, 327.83, T0)

    assert _check(store, 333.83, T0 + timedelta(hours=2))["action"] == "silent"  # +6
    assert _check(store, 337.83, T0 + timedelta(hours=4))["action"] == "notified"  # +10 vs last notification

    assert len(store.history[TRIP.trip_id]) == 3
    previous = sent[-1][2]
    assert previous.price == D("527.83")
    assert store.get_state(TRIP.trip_id).last_notified_price == D("537.83")


def test_trip_thresholds_come_from_config(sent):
    store = InMemoryStore()
    strict = replace(TRIP, min_change_abs=D("100"), min_change_pct=D("50"))
    monitor.check_trip(trip_price(327.83, 200.0, strict), store, NTFY, T0)

    record = monitor.check_trip(trip_price(347.83, 200.0, strict), store, NTFY, T0 + timedelta(hours=2))

    assert record["action"] == "silent"


def test_daily_summary_always_sends_and_resets_baseline(sent):
    store = InMemoryStore()
    _check(store, 327.83, T0)
    _check(store, 321.83, T0 + timedelta(hours=2))  # -6, silent

    record = _check(store, 327.83, T0 + timedelta(hours=14), summary=True)

    assert record["action"] == "summary"
    _, _, previous, stats = sent[-1]
    assert previous.price == D("527.83")
    assert stats == notify.DailyStats(min_price=D("521.83"), max_price=D("527.83"), changes=3)
    assert store.get_state(TRIP.trip_id).last_notified_at == (T0 + timedelta(hours=14)).isoformat()
