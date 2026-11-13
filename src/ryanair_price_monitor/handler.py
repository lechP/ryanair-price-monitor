"""AWS Lambda entry point: price all configured trips and send each result to ntfy.

Topics are read from SSM Parameter Store (SecureString) so they never appear in
Terraform state or Lambda environment variables. Any failure is reported to a
separate error topic and then re-raised so the invocation is marked as failed.
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from functools import cache
from pathlib import Path

from ryanair import Ryanair

from ryanair_price_monitor import notify
from ryanair_price_monitor.prices import fetch_trip_price, load_config

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


def run(price_topic: notify.NtfyConfig, config_path: Path) -> list[dict]:
    currency, trips = load_config(config_path)
    client = Ryanair(currency=currency)
    results = []
    for trip in trips:
        result = fetch_trip_price(client, trip)
        record = {
            "trip": trip.name,
            "outbound": result.outbound.price if result.outbound else None,
            "inbound": result.inbound.price if result.inbound else None,
            "total": result.total,
            "currency": result.currency,
        }
        logger.info(json.dumps(record))
        notify.send(price_topic, result)
        results.append(record)
    return results


def lambda_handler(event: dict, context: object) -> dict:
    price_topic, error_topic = _ntfy_configs()
    try:
        return {"results": run(price_topic, CONFIG_PATH)}
    except Exception as exc:
        logger.exception("Price check failed")
        try:
            message = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc(limit=3)}"
            notify.send_error(error_topic, message[:3500])
        except Exception:
            logger.exception("Could not send error notification")
        raise
