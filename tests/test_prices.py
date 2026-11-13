from datetime import date, datetime

from ryanair.types import Flight

from ryanair_price_monitor.prices import TripConfig, TripPrice, format_price

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


def test_total_sums_both_legs():
    result = TripPrice(TRIP, _flight("WRO", "AGP", 316.71), _flight("AGP", "WRO", 211.12))
    assert result.total == 527.83
    assert "Total: 527.83 PLN" in format_price(result)


def test_missing_leg_has_no_total():
    result = TripPrice(TRIP, _flight("WRO", "AGP", 316.71), None)
    assert result.total is None
    assert "Back: no fare found" in format_price(result)
