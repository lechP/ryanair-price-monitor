from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from conftest import flight
from ryanair_price_monitor import handler, notify
from ryanair_price_monitor.state import InMemoryStore

PRICE = notify.NtfyConfig(topic="prices")
ERRORS = notify.NtfyConfig(topic="errors")
CONFIG = Path(__file__).resolve().parents[1] / "config" / "trips.json"


@pytest.fixture
def ryanair(monkeypatch):
    client = MagicMock()
    store = InMemoryStore()
    monkeypatch.setattr(handler, "Ryanair", lambda currency: client)
    monkeypatch.setattr(handler, "_ntfy_configs", lambda: (PRICE, ERRORS))
    monkeypatch.setattr(handler, "_store", lambda: store)
    monkeypatch.setattr(handler, "CONFIG_PATH", CONFIG)
    monkeypatch.delenv("DAILY_SUMMARY_HOUR", raising=False)
    return client


def test_first_run_notifies_price_topic(ryanair, monkeypatch):
    ryanair.get_cheapest_flights.side_effect = [[flight("WRO", "AGP", 316.71)], [flight("AGP", "WRO", 211.12)]]
    sent = []
    monkeypatch.setattr(notify, "send", lambda cfg, result, previous: sent.append(cfg))

    response = handler.lambda_handler({}, None)

    assert response["results"][0]["total"] == 527.83
    assert response["results"][0]["action"] == "notified"
    assert sent == [PRICE]


def test_failure_goes_to_error_topic_and_reraises(ryanair, monkeypatch):
    ryanair.get_cheapest_flights.side_effect = ConnectionError("blocked")
    errors = []
    monkeypatch.setattr(notify, "send_error", lambda cfg, msg: errors.append((cfg, msg)))

    with pytest.raises(ConnectionError):
        handler.lambda_handler({}, None)

    assert errors[0][0] is ERRORS
    assert errors[0][1].startswith("ConnectionError: blocked")


@pytest.mark.parametrize(
    ("utc_hour", "expected"),
    [(20, True), (19, False), (21, False)],  # 20:00 UTC = 21:00 Europe/Warsaw in November
)
def test_summary_hour_uses_local_time(monkeypatch, utc_hour, expected):
    monkeypatch.setenv("DAILY_SUMMARY_HOUR", "21")
    monkeypatch.setenv("SCHEDULE_TIMEZONE", "Europe/Warsaw")
    assert handler.is_summary_run({}, datetime(2026, 11, 15, utc_hour, 0, 4, tzinfo=UTC)) is expected


def test_summary_can_be_forced_by_event(monkeypatch):
    monkeypatch.delenv("DAILY_SUMMARY_HOUR", raising=False)
    assert handler.is_summary_run({"daily_summary": True}, datetime(2026, 11, 15, 9, tzinfo=UTC)) is True
