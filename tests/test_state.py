from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import boto3
import pytest
from moto import mock_aws

from conftest import TRIP, trip_price
from ryanair_price_monitor.state import DynamoStore, TripState

T0 = datetime(2026, 11, 15, 7, 0, tzinfo=UTC)


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
    with mock_aws():
        table = boto3.resource("dynamodb").create_table(
            TableName="prices",
            KeySchema=[{"AttributeName": "trip_id", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[
                {"AttributeName": "trip_id", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoStore(table)


def test_missing_state_is_empty(store):
    assert store.get_state(TRIP.trip_id) == TripState()


def test_state_round_trip(store):
    state = TripState(D("527.83"), "2026-11-15T07:00:00+00:00", None, None)
    store.save_state(TRIP.trip_id, state)
    assert store.get_state(TRIP.trip_id) == state


def test_history_is_filtered_by_time_and_excludes_state(store):
    store.save_state(TRIP.trip_id, TripState(D("1"), "x", None, None))
    store.record_price(TRIP.trip_id, T0, trip_price(327.83, 200.0))
    store.record_price(TRIP.trip_id, T0 + timedelta(hours=26), trip_price(None, 200.0))
    store.record_price(TRIP.trip_id, T0 + timedelta(hours=28), trip_price(317.83, 200.0))

    history = store.price_history(TRIP.trip_id, T0 + timedelta(hours=24))

    assert [p.total for p in history] == [None, D("517.83")]
