from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from ryanair.types import Flight

from ryanair_price_monitor import handler, notify

PRICE = notify.NtfyConfig(topic="prices")
ERRORS = notify.NtfyConfig(topic="errors")
CONFIG = Path(__file__).resolve().parents[1] / "config" / "trips.json"


def _flight(price: float) -> Flight:
    return Flight(
        departureTime=datetime(2027, 1, 14, 16, 45),
        flightNumber="FR 1234",
        price=price,
        currency="PLN",
        origin="WRO",
        originFull="WRO",
        destination="AGP",
        destinationFull="AGP",
    )


@pytest.fixture
def ryanair(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(handler, "Ryanair", lambda currency: client)
    monkeypatch.setattr(handler, "_ntfy_configs", lambda: (PRICE, ERRORS))
    monkeypatch.setattr(handler, "CONFIG_PATH", CONFIG)
    return client


def test_sends_price_per_trip(ryanair, monkeypatch):
    ryanair.get_cheapest_flights.side_effect = [[_flight(316.71)], [_flight(211.12)]]
    sent = []
    monkeypatch.setattr(notify, "send", lambda cfg, result: sent.append((cfg, result)))

    response = handler.lambda_handler({}, None)

    assert response["results"][0]["total"] == 527.83
    assert sent[0][0] is PRICE


def test_failure_goes_to_error_topic_and_reraises(ryanair, monkeypatch):
    ryanair.get_cheapest_flights.side_effect = ConnectionError("blocked")
    errors = []
    monkeypatch.setattr(notify, "send_error", lambda cfg, msg: errors.append((cfg, msg)))

    with pytest.raises(ConnectionError):
        handler.lambda_handler({}, None)

    assert errors[0][0] is ERRORS
    assert errors[0][1].startswith("ConnectionError: blocked")
