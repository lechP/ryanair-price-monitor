"""Local entry point: print current prices for all configured trips."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ryanair import Ryanair

from ryanair_price_monitor.prices import fetch_trip_price, format_price, load_config

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "trips.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    currency, trips = load_config(args.config)
    client = Ryanair(currency=currency)
    for trip in trips:
        print(format_price(fetch_trip_price(client, trip)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
