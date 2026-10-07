# Local Lead Generation

A small, modular CLI for collecting local business leads, normalizing and scoring them, persisting to SQLite, and exporting JSON/CSV.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[test]'
cp .env.example .env
```

`APIFY_API_TOKEN` is required for Places. Places searches run the `compass/crawler-google-places` Apify actor and then retrieve its default dataset through a secure Authorization header. The `web` source is currently feature-disabled; no Google HTML request is made. Social connectors are intentionally feature-disabled stubs. Never commit credentials; `.env.example` contains placeholders only.

## Usage

```bash
leadgen search plumbers "Austin, TX" --source places
leadgen search dentists "Austin, TX" --source web
leadgen export leads.json --format json
leadgen export leads.csv --format csv
pytest
```

No secrets are included in this repository.
