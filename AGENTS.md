# AGENTS.md

- All code, comments, docs, and commit messages in this repository are written in English.
- Python 3.12 project managed with uv; run tests with `uv run pytest`.
- Price logic lives in `src/ryanair_price_monitor/prices.py` and must stay free of AWS dependencies so it runs both locally (`cli.py`) and in Lambda.
- The Ryanair API is unofficial; keep requests to a minimum (one call per leg per check) and do not add aggressive retries.
- This is a personal project deployed to a private AWS account. Do not use the Ocado SSO config (`~/.aws/ocado-config`) here.
- Infrastructure will be managed with Terraform under `infra/`. Never commit state files or `*.tfvars` with secrets.
- The ntfy topic name acts as a secret; keep it out of the repository.
