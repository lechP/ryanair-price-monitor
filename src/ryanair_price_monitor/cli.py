"""Local entry point: print current prices for all configured trips, optionally sending them to ntfy."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ryanair import Ryanair

from ryanair_price_monitor import notify
from ryanair_price_monitor.prices import fetch_trip_price, format_price, load_config

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "trips.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--notify",
        action="store_true",
        help="send each result to ntfy (reads NTFY_TOPIC, NTFY_SERVER, NTFY_TOKEN)",
    )
    args = parser.parse_args()

    ntfy_config = notify.NtfyConfig.from_env() if args.notify else None
    currency, trips = load_config(args.config)
    client = Ryanair(currency=currency)
    for trip in trips:
        result = fetch_trip_price(client, trip)
        print(format_price(result))
        if ntfy_config:
            notify.send(ntfy_config, result)
            print("Sent to ntfy.")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
