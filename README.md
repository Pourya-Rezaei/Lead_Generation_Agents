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

### Local web panel

Start the browser-based panel from the project root:

```bash
uvicorn src.web.app:app --host 127.0.0.1 --port 8000
```

Then open <http://127.0.0.1:8000>. The MVP supports Campaign management, synchronous Places searches, Campaign lead viewing, and JSON/CSV downloads. It binds to localhost only and does not expose the panel to the network.

A search without `--campaign` is stored in the default `general` campaign. Export without `--campaign` includes all unique leads; adding a campaign ID limits the export to leads associated with that campaign. Campaigns share canonical lead records, so a business found in multiple campaigns is not duplicated globally.

Social search contract

`SocialSearchService` is a provider-independent, API/CLI-facing validation boundary. A request selects one or more declared social sources and uses either explicit HTTPS `profile_urls` or keyword mode (`query`, optionally `location`), never both. Source capability descriptors are checked before execution; Instagram, TikTok, and web Actors remain disabled; LinkedIn Jobs is enabled only through the campaign source path after its contract gate passes. Platform-specific `PlatformSearchResult` observations are returned unchanged when a test or future enabled executor is supplied. No paid Actor is enabled by this phase.

### Multi-source orchestration

The web search form accepts one or more enabled discovery sources (`places` and `google_search`). Each source runs independently through `MultiSourceOrchestrator`; successful results are persisted even when another source fails, and a partial result is reported instead of discarding completed work. Disabled social sources remain visible in the UI but are rejected before execution. For asynchronous integrations, `POST /api/orchestrated-searches` validates sources and creates an idempotent Job; workers can execute its `sources` list with `multi_source_handler` and preserve `succeeded`, `partial`, or `failed` state.

No secrets are included in this repository.

### Social Actor contract status (Phase E)

Instagram and TikTok remain disabled. LinkedIn Jobs is contract-verified for controlled campaign execution. Official Apify Store metadata: Instagram is listed at **$1.50/1,000 results**, TikTok at **$1.70/1,000 results**, and LinkedIn Jobs at approximately **$0.0008/job result**. LinkedIn Jobs uses the verified `keywords`, `location`, `maxResults`, `scrapeDetails`, and `scrapeCompany` input contract; Instagram and TikTok remain unverified. See `docs/06-apify-integration.md` for the official URLs and gate model.

### Container deployment

Build and run the production image locally:

```bash
docker build -t local-lead-generation .
mkdir -p data && sudo chown 10001:10001 data
docker run --rm -p 8000:8000 -v "$(pwd)/data:/data" \
	-e APIFY_API_TOKEN="$APIFY_API_TOKEN" local-lead-generation
```

The SQLite database is stored at `/data/leads.db`. For Render, use the included `render.yaml` and configure `APIFY_API_TOKEN` as a secret. For Kubernetes, publish the image, update the image reference in `k8s/deployment.yaml`, create the secret from `k8s/secret.example.yaml`, then apply `k8s/pvc.yaml`, `k8s/deployment.yaml`, and `k8s/service.yaml`. Keep one replica unless the storage layer is changed from SQLite to a server database.
