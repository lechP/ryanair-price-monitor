"""Fetch the cheapest Ryanair return fare for a configured trip."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ryanair import Ryanair
from ryanair.types import Flight


@dataclass(frozen=True)
class TripConfig:
    name: str
    origin: str
    destination: str
    outbound_date: date
    inbound_date: date

    @classmethod
    def from_dict(cls, data: dict) -> TripConfig:
        return cls(
            name=data["name"],
            origin=data["origin"],
            destination=data["destination"],
            outbound_date=date.fromisoformat(data["outbound_date"]),
            inbound_date=date.fromisoformat(data["inbound_date"]),
        )


@dataclass(frozen=True)
class TripPrice:
    trip: TripConfig
    outbound: Flight | None
    inbound: Flight | None

    @property
    def total(self) -> float | None:
        if self.outbound is None or self.inbound is None:
            return None
        return round(self.outbound.price + self.inbound.price, 2)

    @property
    def currency(self) -> str | None:
        flight = self.outbound or self.inbound
        return flight.currency if flight else None


def load_config(path: Path) -> tuple[str, list[TripConfig]]:
    data = json.loads(path.read_text())
    return data["currency"], [TripConfig.from_dict(t) for t in data["trips"]]


def _cheapest_one_way(client: Ryanair, origin: str, destination: str, day: date) -> Flight | None:
    flights = client.get_cheapest_flights(origin, day, day, destination_airport=destination)
    return min(flights, key=lambda f: f.price) if flights else None


def fetch_trip_price(client: Ryanair, trip: TripConfig) -> TripPrice:
    """Price both legs as one-way fares; Ryanair prices a return as two one-ways."""
    outbound = _cheapest_one_way(client, trip.origin, trip.destination, trip.outbound_date)
    inbound = _cheapest_one_way(client, trip.destination, trip.origin, trip.inbound_date)
    return TripPrice(trip=trip, outbound=outbound, inbound=inbound)


def format_price(result: TripPrice) -> str:
    lines = [result.trip.name]
    for label, flight in (("Out", result.outbound), ("Back", result.inbound)):
        if flight is None:
            lines.append(f"{label}: no fare found")
        else:
            lines.append(
                f"{label}: {flight.origin}->{flight.destination} "
                f"{flight.departureTime:%Y-%m-%d %H:%M} {flight.flightNumber} "
                f"{flight.price:.2f} {flight.currency}"
            )
    total = result.total
    lines.append(f"Total: {total:.2f} {result.currency}" if total is not None else "Total: n/a")
    return "\n".join(lines)
