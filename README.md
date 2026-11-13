# ryanair-price-monitor

Checks the price of a specific Ryanair return trip several times a day and sends the result to a phone.

Prices come from Ryanair's unofficial fare-finder API (`services-api.ryanair.com/farfnd/v4/oneWayFares`) through the [`ryanair-py`](https://pypi.org/project/ryanair-py/) library. Each leg is priced as the cheapest one-way fare on its date, and the total is the sum of both legs. These are cached fares, so they can differ slightly from the price shown at booking.

## Status

- [x] Local price check
- [x] Notifications via [ntfy.sh](https://ntfy.sh)
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

## Notifications (ntfy)

1. Pick a hard-to-guess topic name, e.g. `python3 -c "import secrets; print('ryanair-' + secrets.token_urlsafe(16))"`. Anyone who knows the topic can read and post to it, so keep it out of the repository.
2. Install the ntfy app on the phone and subscribe to that topic on `ntfy.sh`.
3. Put the topic in `.env` in the repository root (copy `.env.example` if `.env` does not exist; `.env` is gitignored):

```
NTFY_TOPIC=<your-topic>
```

4. Send the current prices with [scripts/send-test-notification.sh](scripts/send-test-notification.sh) (run it from the IDE or a terminal):

```bash
./scripts/send-test-notification.sh
```

Each trip becomes one notification titled `WRO-AGP: 527.83 PLN`, with both legs in the body. Expand the notification (long press) to see two buttons: **Ryanair app** opens the app's home screen, and **Website** opens the Ryanair search for those dates in the browser. The app has no documented deep link for a route search, so the dated search is web only. If a leg has no fare, the notification is sent with high priority.

Optional variables: `NTFY_SERVER` (default `https://ntfy.sh`) and `NTFY_TOKEN` (bearer token for a protected topic or a self-hosted server).

## Tests

```bash
uv run pytest
```
