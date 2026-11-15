"""Price history and per-trip notification state.

DynamoDB layout (one table):
  trip_id = "<ORIGIN>-<DEST>-<OUT DATE>-<IN DATE>"
  sk = "STATE"             -> last_price, last_checked_at, last_notified_price, last_notified_at
  sk = "PRICE#<ISO time>"  -> total, outbound, inbound, currency (only written when the price changes)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from ryanair_price_monitor.prices import TripPrice

STATE_SK = "STATE"
PRICE_PREFIX = "PRICE#"


@dataclass
class TripState:
    last_price: Decimal | None = None
    last_checked_at: str | None = None
    last_notified_price: Decimal | None = None
    last_notified_at: str | None = None

    @property
    def checked_before(self) -> bool:
        return self.last_checked_at is not None

    @property
    def notified_before(self) -> bool:
        return self.last_notified_at is not None


@dataclass(frozen=True)
class PricePoint:
    at: str
    total: Decimal | None


class PriceStore(Protocol):
    def get_state(self, trip_id: str) -> TripState: ...

    def save_state(self, trip_id: str, state: TripState) -> None: ...

    def record_price(self, trip_id: str, at: datetime, result: TripPrice) -> None: ...

    def price_history(self, trip_id: str, since: datetime) -> list[PricePoint]: ...


def _iso(at: datetime) -> str:
    return at.isoformat(timespec="seconds")


def _decimal(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _price_item(result: TripPrice) -> dict:
    return {
        "total": result.total_decimal,
        "outbound": _decimal(result.outbound.price) if result.outbound else None,
        "inbound": _decimal(result.inbound.price) if result.inbound else None,
        "currency": result.currency,
    }


class InMemoryStore:
    """Used by tests and local experiments."""

    def __init__(self) -> None:
        self.states: dict[str, TripState] = {}
        self.history: dict[str, list[tuple[str, dict]]] = {}

    def get_state(self, trip_id: str) -> TripState:
        state = self.states.get(trip_id)
        return TripState(**vars(state)) if state else TripState()

    def save_state(self, trip_id: str, state: TripState) -> None:
        self.states[trip_id] = TripState(**vars(state))

    def record_price(self, trip_id: str, at: datetime, result: TripPrice) -> None:
        self.history.setdefault(trip_id, []).append((_iso(at), _price_item(result)))

    def price_history(self, trip_id: str, since: datetime) -> list[PricePoint]:
        cutoff = _iso(since)
        return [PricePoint(at, item["total"]) for at, item in self.history.get(trip_id, []) if at >= cutoff]


class DynamoStore:
    def __init__(self, table) -> None:
        self.table = table

    @classmethod
    def from_table_name(cls, name: str) -> DynamoStore:
        import boto3  # provided by the Lambda runtime

        return cls(boto3.resource("dynamodb").Table(name))

    def get_state(self, trip_id: str) -> TripState:
        item = self.table.get_item(Key={"trip_id": trip_id, "sk": STATE_SK}).get("Item")
        if not item:
            return TripState()
        return TripState(
            last_price=item.get("last_price"),
            last_checked_at=item.get("last_checked_at"),
            last_notified_price=item.get("last_notified_price"),
            last_notified_at=item.get("last_notified_at"),
        )

    def save_state(self, trip_id: str, state: TripState) -> None:
        self.table.put_item(Item={"trip_id": trip_id, "sk": STATE_SK, **vars(state)})

    def record_price(self, trip_id: str, at: datetime, result: TripPrice) -> None:
        self.table.put_item(Item={"trip_id": trip_id, "sk": PRICE_PREFIX + _iso(at), **_price_item(result)})

    def price_history(self, trip_id: str, since: datetime) -> list[PricePoint]:
        from boto3.dynamodb.conditions import Key

        response = self.table.query(
            KeyConditionExpression=Key("trip_id").eq(trip_id)
            & Key("sk").between(PRICE_PREFIX + _iso(since), PRICE_PREFIX + "~"),
        )
        return [PricePoint(item["sk"].removeprefix(PRICE_PREFIX), item.get("total")) for item in response["Items"]]
