# ryanair-price-monitor

Checks the price of a specific Ryanair return trip several times a day and sends the result to a phone.

Prices come from Ryanair's unofficial fare-finder API (`services-api.ryanair.com/farfnd/v4/oneWayFares`) through the [`ryanair-py`](https://pypi.org/project/ryanair-py/) library. Each leg is priced as the cheapest one-way fare on its date, and the total is the sum of both legs. These are cached fares, so they can differ slightly from the price shown at booking.

## Status

- [x] Local price check
- [ ] Notifications via [ntfy.sh](https://ntfy.sh)
- [ ] AWS Lambda + EventBridge Scheduler (every 2 hours, 08:00–20:00 Europe/Warsaw), deployed with Terraform

## Configuration

Trips are defined in [config/trips.json](config/trips.json): currency plus a list of trips with `origin`, `destination`, `outbound_date` and `inbound_date` (IATA codes, ISO dates).

## Local usage

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python -m ryanair_price_monitor.cli
uv run python -m ryanair_price_monitor.cli --config path/to/trips.json
```

Example output:

```
WRO-AGP January 2027
Out: WRO->AGP 2027-01-14 16:45 FR 2582 316.71 PLN
Back: AGP->WRO 2027-01-21 21:05 FR 2581 211.12 PLN
Total: 527.83 PLN
```

## Tests

```bash
uv run pytest
```
