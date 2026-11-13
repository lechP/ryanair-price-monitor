# ryanair-price-monitor

Checks the price of a specific Ryanair return trip several times a day and sends the result to a phone.

Prices come from Ryanair's unofficial fare-finder API (`services-api.ryanair.com/farfnd/v4/oneWayFares`) through the [`ryanair-py`](https://pypi.org/project/ryanair-py/) library. Each leg is priced as the cheapest one-way fare on its date, and the total is the sum of both legs. These are cached fares, so they can differ slightly from the price shown at booking.

## Status

- [x] Local price check
- [x] Notifications via [ntfy.sh](https://ntfy.sh)
- [x] AWS Lambda + EventBridge Scheduler (every 2 hours, 08:00–20:00 Europe/Warsaw), defined in Terraform
- [ ] First deployment

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

## AWS deployment

Infrastructure lives in [infra/](infra/) (Terraform, region `eu-central-1`):

- Lambda `ryanair-price-monitor` (Python 3.12, arm64) running `ryanair_price_monitor.handler.lambda_handler`, with Lambda retries disabled.
- EventBridge Scheduler `cron(0 8-20/2 * * ? *)` in `Europe/Warsaw`: 08:00, 10:00, …, 20:00, no retries.
- CloudWatch log group with 14-day retention; each check logs one JSON line with the prices.
- IAM roles for the Lambda (logs, read two SSM parameters) and the scheduler (invoke the Lambda).

Prices go to the ntfy topic in SSM parameter `/ryanair-price-monitor/ntfy-topic`. Any failure goes to a separate topic in `/ryanair-price-monitor/ntfy-error-topic` with high priority. Both parameters are created by hand so the topic names never appear in Terraform state.

All commands below assume the private AWS profile:

```bash
export AWS_CONFIG_FILE=~/.aws/private-config AWS_PROFILE=<profile>
aws sts get-caller-identity
```

### One-time setup

1. Create the state bucket (local state, kept in `infra/bootstrap/`):

```bash
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap apply
terraform -chdir=infra/bootstrap output -raw backend_config > infra/backend.hcl
```

2. Create both ntfy topic parameters (subscribe to both topics in the phone app):

```bash
aws ssm put-parameter --region eu-central-1 --type SecureString --name /ryanair-price-monitor/ntfy-topic --value '<price-topic>'
aws ssm put-parameter --region eu-central-1 --type SecureString --name /ryanair-price-monitor/ntfy-error-topic --value '<error-topic>'
```

3. Initialise the main stack:

```bash
terraform -chdir=infra init -backend-config=backend.hcl
```

### Deploy

```bash
./scripts/build-lambda.sh
terraform -chdir=infra apply
```

Changing [config/trips.json](config/trips.json) requires the same two commands.

### Manual check

```bash
aws lambda invoke --region eu-central-1 --function-name ryanair-price-monitor /dev/stdout
aws logs tail --region eu-central-1 /aws/lambda/ryanair-price-monitor --since 1h
```

## Tests

```bash
uv run pytest
```
