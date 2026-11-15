from datetime import date, datetime

from ryanair.types import Flight

from ryanair_price_monitor.prices import TripConfig, TripPrice

TRIP = TripConfig("Test", "WRO", "AGP", date(2027, 1, 14), date(2027, 1, 21))


def flight(origin: str, destination: str, price: float) -> Flight:
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


def trip_price(outbound: float | None, inbound: float | None, trip: TripConfig = TRIP) -> TripPrice:
    return TripPrice(
        trip,
        flight("WRO", "AGP", outbound) if outbound is not None else None,
        flight("AGP", "WRO", inbound) if inbound is not None else None,
    )
