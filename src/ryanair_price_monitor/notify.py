"""Send trip prices to a phone through ntfy (https://ntfy.sh)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlencode

import requests

from ryanair_price_monitor.prices import TripPrice, format_price

DEFAULT_SERVER = "https://ntfy.sh"
TIMEOUT_SECONDS = 10
# Only path on Ryanair's domains registered as an iOS universal link; it opens the app's home screen.
# The app ignores route and date parameters, so the dated search is offered as a separate web button.
APP_URL = "https://app.ryanair.com/store/ios"


@dataclass(frozen=True)
class NtfyConfig:
    topic: str
    server: str = DEFAULT_SERVER
    token: str | None = None

    @classmethod
    def from_env(cls) -> NtfyConfig:
        topic = os.environ.get("NTFY_TOPIC")
        if not topic:
            raise RuntimeError("NTFY_TOPIC is not set")
        return cls(
            topic=topic,
            server=os.environ.get("NTFY_SERVER", DEFAULT_SERVER).rstrip("/"),
            token=os.environ.get("NTFY_TOKEN") or None,
        )


def booking_url(result: TripPrice) -> str:
    trip = result.trip
    params = {
        "adults": 1,
        "teens": 0,
        "children": 0,
        "infants": 0,
        "dateOut": trip.outbound_date.isoformat(),
        "dateIn": trip.inbound_date.isoformat(),
        "isConnectedFlight": "false",
        "isReturn": "true",
        "discount": 0,
        "originIata": trip.origin,
        "destinationIata": trip.destination,
    }
    return "https://www.ryanair.com/pl/pl/trip/flights/select?" + urlencode(params)


def build_message(result: TripPrice) -> tuple[str, str, dict[str, str]]:
    """Return (title, body, extra headers) for one trip."""
    trip = result.trip
    total = result.total
    price = f"{total:.2f} {result.currency}" if total is not None else "no fare"
    title = f"{trip.origin}-{trip.destination}: {price}"
    body = format_price(result)
    headers = {
        "Tags": "airplane" if total is not None else "warning",
        "Priority": "default" if total is not None else "high",
        "Actions": f"view, Ryanair app, {APP_URL}; view, Website, {booking_url(result)}",
    }
    return title, body, headers


def send(config: NtfyConfig, result: TripPrice, session: requests.Session | None = None) -> None:
    title, body, headers = build_message(result)
    headers["Title"] = title
    if config.token:
        headers["Authorization"] = f"Bearer {config.token}"
    http = session or requests
    response = http.post(
        f"{config.server}/{config.topic}",
        data=body.encode("utf-8"),
        headers=headers,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
