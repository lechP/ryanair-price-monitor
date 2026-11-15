"""AWS Lambda entry point: price all configured trips, store changes, notify on significant moves.

A notification is sent when the total moved by at least the configured amount or
percentage since the last notification. The run at DAILY_SUMMARY_HOUR (local time in
SCHEDULE_TIMEZONE) always sends a low-priority daily summary instead. Invoke with
{"daily_summary": true} to force a summary.

Topics are read from SSM Parameter Store (SecureString) so they never appear in
Terraform state or Lambda environment variables. Any failure is reported to a
separate error topic and then re-raised so the invocation is marked as failed.
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from zoneinfo import ZoneInfo

from ryanair import Ryanair

from ryanair_price_monitor import monitor, notify
from ryanair_price_monitor.prices import fetch_trip_price, load_config
from ryanair_price_monitor.state import DynamoStore, PriceStore

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# In the Lambda package the module sits at /var/task/ryanair_price_monitor/handler.py
# and the config at /var/task/config/trips.json.
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "trips.json"


@cache
def _ntfy_configs() -> tuple[notify.NtfyConfig, notify.NtfyConfig]:
    import boto3  # provided by the Lambda runtime

    ssm = boto3.client("ssm")
    names = [os.environ["NTFY_TOPIC_PARAMETER"], os.environ["NTFY_ERROR_TOPIC_PARAMETER"]]
    response = ssm.get_parameters(Names=names, WithDecryption=True)
    if response["InvalidParameters"]:
        raise RuntimeError(f"Missing SSM parameters: {response['InvalidParameters']}")
    values = {p["Name"]: p["Value"] for p in response["Parameters"]}
    server = os.environ.get("NTFY_SERVER", notify.DEFAULT_SERVER).rstrip("/")
    return (
        notify.NtfyConfig(topic=values[names[0]], server=server),
        notify.NtfyConfig(topic=values[names[1]], server=server),
    )


@cache
def _store() -> PriceStore:
    return DynamoStore.from_table_name(os.environ["TABLE_NAME"])


def is_summary_run(event: dict, now: datetime) -> bool:
    if event.get("daily_summary") is True:
        return True
    hour = os.environ.get("DAILY_SUMMARY_HOUR")
    if hour is None:
        return False
    local = now.astimezone(ZoneInfo(os.environ.get("SCHEDULE_TIMEZONE", "Europe/Warsaw")))
    return local.hour == int(hour)


def run(
    price_topic: notify.NtfyConfig,
    store: PriceStore,
    config_path: Path,
    now: datetime,
    daily_summary: bool,
) -> list[dict]:
    currency, trips = load_config(config_path)
    client = Ryanair(currency=currency)
    records = []
    for trip in trips:
        result = fetch_trip_price(client, trip)
        record = monitor.check_trip(result, store, price_topic, now, daily_summary)
        logger.info(json.dumps(record))
        records.append(record)
    return records


def lambda_handler(event: dict, context: object) -> dict:
    price_topic, error_topic = _ntfy_configs()
    try:
        now = datetime.now(UTC)
        summary = is_summary_run(event or {}, now)
        return {"results": run(price_topic, _store(), CONFIG_PATH, now, summary)}
    except Exception as exc:
        logger.exception("Price check failed")
        try:
            message = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc(limit=3)}"
            notify.send_error(error_topic, message[:3500])
        except Exception:
            logger.exception("Could not send error notification")
        raise
