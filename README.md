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
leadgen campaign create "Austin plumbers" --id austin-plumbers
leadgen campaign list
leadgen search plumbers "Austin, TX" --source places --campaign austin-plumbers
leadgen campaign show austin-plumbers
leadgen export leads.json --format json --campaign austin-plumbers
leadgen export leads.csv --format csv
pytest
```

A search without `--campaign` is stored in the default `general` campaign. Export without `--campaign` includes all unique leads; adding a campaign ID limits the export to leads associated with that campaign. Campaigns share canonical lead records, so a business found in multiple campaigns is not duplicated globally.

No secrets are included in this repository.
