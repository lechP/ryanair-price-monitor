"""Send trip prices to a phone through ntfy (https://ntfy.sh)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
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


@dataclass(frozen=True)
class Previous:
    """The price the user last saw in a notification."""

    price: Decimal | None
    at: str


@dataclass(frozen=True)
class DailyStats:
    min_price: Decimal | None
    max_price: Decimal | None
    changes: int


def _money(value: Decimal | float | None, currency: str | None) -> str:
    return f"{value:.2f} {currency}" if value is not None else "no fare"


def _change(current: Decimal | None, previous: Previous | None) -> str | None:
    """Signed change such as "-12.43, -2.4%" or None when there is nothing to compare."""
    if previous is None or previous.price is None or current is None:
        return None
    diff = current - previous.price
    pct = diff / previous.price * 100 if previous.price else Decimal(0)
    return f"{diff:+.2f}, {pct:+.1f}%"


def _trend_tag(current: Decimal | None, previous: Previous | None) -> str:
    if current is None:
        return "warning"
    if previous is None or previous.price is None or current == previous.price:
        return "airplane"
    return "chart_with_downwards_trend" if current < previous.price else "chart_with_upwards_trend"


def _actions(result: TripPrice) -> str:
    return f"view, Ryanair app, {APP_URL}; view, Website, {booking_url(result)}"


def build_message(result: TripPrice, previous: Previous | None = None) -> tuple[str, str, dict[str, str]]:
    """Return (title, body, extra headers) for a price notification."""
    trip = result.trip
    current = result.total_decimal
    title = f"{trip.origin}-{trip.destination}: {_money(current, result.currency)}"
    change = _change(current, previous)
    if change:
        title += f" ({change})"
    body = format_price(result)
    if previous is not None:
        body += f"\nPreviously notified: {_money(previous.price, result.currency)} at {previous.at}"
    headers = {
        "Tags": _trend_tag(current, previous),
        "Priority": "default" if current is not None else "high",
        "Actions": _actions(result),
    }
    return title, body, headers


def build_summary(
    result: TripPrice, previous: Previous | None, stats: DailyStats
) -> tuple[str, str, dict[str, str]]:
    """Return (title, body, extra headers) for the low-priority daily summary."""
    trip = result.trip
    current = result.total_decimal
    currency = result.currency
    title = f"Daily {trip.origin}-{trip.destination}: {_money(current, currency)}"
    lines = [format_price(result)]
    change = _change(current, previous)
    if change:
        lines.append(f"Since last notification ({previous.at}): {change}")
    lines.append(
        f"Last 24h: min {_money(stats.min_price, currency)}, max {_money(stats.max_price, currency)}, "
        f"{stats.changes} price change(s)"
    )
    headers = {"Tags": "calendar", "Priority": "low", "Actions": _actions(result)}
    return title, "\n".join(lines), headers


def send(
    config: NtfyConfig,
    result: TripPrice,
    previous: Previous | None = None,
    session: requests.Session | None = None,
) -> None:
    title, body, headers = build_message(result, previous)
    _post(config, title, body, headers, session)


def send_summary(
    config: NtfyConfig,
    result: TripPrice,
    previous: Previous | None,
    stats: DailyStats,
    session: requests.Session | None = None,
) -> None:
    title, body, headers = build_summary(result, previous, stats)
    _post(config, title, body, headers, session)


def send_error(config: NtfyConfig, message: str, session: requests.Session | None = None) -> None:
    headers = {"Tags": "rotating_light", "Priority": "high"}
    _post(config, "ryanair-price-monitor failed", message, headers, session)


def _post(
    config: NtfyConfig,
    title: str,
    body: str,
    headers: dict[str, str],
    session: requests.Session | None,
) -> None:
    headers = {**headers, "Title": title}
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
