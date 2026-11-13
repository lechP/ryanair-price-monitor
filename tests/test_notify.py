from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from ryanair.types import Flight

from ryanair_price_monitor import notify
from ryanair_price_monitor.prices import TripConfig, TripPrice

TRIP = TripConfig("Test", "WRO", "AGP", date(2027, 1, 14), date(2027, 1, 21))


def _flight(origin: str, destination: str, price: float) -> Flight:
    return Flight(
        departureTime=datetime(2027, 1, 14, 16, 45),
        flightNumber="FR 1234",
        price=price,
        currency="PLN",
        origin=origin,
        originFull=origin,
        destination=destination,
        destinationFull=destination,
    )


def test_send_posts_price_to_topic():
    session = MagicMock()
    result = TripPrice(TRIP, _flight("WRO", "AGP", 316.71), _flight("AGP", "WRO", 211.12))

    notify.send(notify.NtfyConfig(topic="secret-topic", token="tk"), result, session=session)

    url = session.post.call_args.args[0]
    kwargs = session.post.call_args.kwargs
    assert url == "https://ntfy.sh/secret-topic"
    assert kwargs["headers"]["Title"] == "WRO-AGP: 527.83 PLN"
    assert kwargs["headers"]["Authorization"] == "Bearer tk"
    assert "Click" not in kwargs["headers"]
    app_action, web_action = kwargs["headers"]["Actions"].split("; ")
    assert app_action == f"view, Ryanair app, {notify.APP_URL}"
    assert web_action.startswith("view, Website, https://www.ryanair.com/")
    assert "dateOut=2027-01-14" in web_action
    assert b"Total: 527.83 PLN" in kwargs["data"]
    session.post.return_value.raise_for_status.assert_called_once()


def test_missing_fare_is_high_priority():
    title, _, headers = notify.build_message(TripPrice(TRIP, None, None))
    assert title == "WRO-AGP: no fare"
    assert headers["Priority"] == "high"


def test_config_requires_topic(monkeypatch):
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    with pytest.raises(RuntimeError):
        notify.NtfyConfig.from_env()


def test_send_error_is_high_priority():
    session = MagicMock()

    notify.send_error(notify.NtfyConfig(topic="errors"), "boom", session=session)

    kwargs = session.post.call_args.kwargs
    assert session.post.call_args.args[0] == "https://ntfy.sh/errors"
    assert kwargs["headers"]["Priority"] == "high"
    assert kwargs["data"] == b"boom"
