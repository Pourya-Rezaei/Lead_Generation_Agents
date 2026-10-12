# Local Lead Generation

## Independent Instagram campaigns (2026-10-12)

Instagram now requires an explicitly selected **Instagram campaign**; Places campaigns and Lead exports are unchanged. Create/list campaigns at `/instagram-campaigns`, inspect profiles and run history at `/instagram-campaigns/{campaign_id}`, then select the campaign on `/search?source=instagram`. Empty lists link to campaign creation. Existing Instagram runs remain run-exportable but are **not automatically imported**.

Campaign JSON/CSV downloads use `/instagram-campaigns/{campaign_id}/export?format=json|csv`. Source-specific fields remain `source_id` (provider ID), `username`, `full_name` (display name), `source_url` (canonical profile URL), `biography`, `external_links`, and existing optional fields. Unicode JSON and UTF-8 BOM CSV preserve Persian; CSV cells mitigate spreadsheet formulas, including leading whitespace. Only validated public profiles and safe HTTP(S) links are retained; business status remains optional and is not verified business evidence. No contacts are inferred from biography.

CLI examples: `instagram-campaign create "کافه‌ها" --campaign cafes`, `instagram-campaign list`, `instagram-search "کافه تهران" --campaign cafes`, `jobs submit-instagram "کافه تهران" --campaign cafes --idempotency-key KEY`, `instagram-campaign export cafes profiles.csv --format csv`. Existing `instagram-export RUN_ID OUTPUT` remains available. APIs: `GET/POST /api/instagram-campaigns`; `POST /api/jobs` includes `source=instagram`, `search`, `searchLimit`, `campaign_id`, and `idempotency_key`. Missing or Places-only selections are rejected before provider execution.

SQLite migration **18** adds separate campaign/run/profile-observation tables without moving historical data. Run payloads and observations commit atomically; replayed successful run IDs are immutable and cannot switch campaigns. Aggregation prefers stable provider IDs, falls back to case-insensitive canonical usernames, and selects the latest valid observation by `(started_at, run_id)` descending. Renamed stable IDs stay one profile; distinct IDs sharing a reused username remain distinct. Failed/empty runs remain in history and never erase prior profiles. Instagram cache identity is campaign-specific and versioned independently from historical run storage.

**Deployment:** stop the owned web server and worker together before migration; restart them with this code against the same database. Migration runs at initialization. The implementation/tests did not open or migrate the live database, restart running sessions, or call paid Actors. Do not roll back to a schema-17 binary after migrating.


## Current two-source release (2026-10-11)

The executable product supports only **Google Places** and **independent Instagram Search**. Places retains its query/location/limit contract. Instagram uses `apify~instagram-search-scraper`: exactly one editable `search` phrase (comma-separated terms rejected), `searchLimit` defaults to 10 and accepts 1..250, `searchType=user`, `liveSearch=false`, and `enhanceUserSearchWithFacebookPage=false`. No old `resultsType`, `directUrls`, or `addParentData` is sent.

Select a source at `/search` before its separate form. Instagram jobs contain `source`, `search`, and `searchLimit`, not a fabricated location. Only explicitly public (`private=false`) profiles are accepted. Business status is optional and is not proof of a verified business. Names and canonical links, optional public biography, safe external links and aggregate counts are retained; contacts are not extracted from biography. Posts, comments, audience lists, Facebook data and email enrichment are discarded at ingestion. Geography is not guaranteed; absent address is not an error.

Google Search, LinkedIn Jobs, YouTube, TikTok and the old Instagram enrichment workflow are **historical, non-executable**. Existing database rows are preserved without schema redesign. Old requests cannot start, retry, resume or replay cache; generic job history/provider-attempt information and safe abandonment remain available. The older sections below that discuss these sources describe previous releases, not current capabilities.

Instagram profiles persist in existing run metadata and allowlisted raw records, never as fabricated Leads. Reload/export is scoped to one independent run; campaign Lead exports retain existing Places and historical Lead rows, and do not fabricate Instagram Leads. Historical profile candidates remain read-only. JSON/CSV downloads: `/api/instagram-runs/{run_id}/export/{json|csv}`. CLI: `instagram-search "phrase" --search-limit 10`, `jobs submit-instagram "phrase" --idempotency-key KEY`, and `instagram-export RUN_ID OUTPUT --format json`. API `/api/jobs` accepts a single source-specific request plus `idempotency_key`; multi-source/social/enrichment public routes are removed.

Provider run IDs are journaled before polling; resume uses the same known run. Unknown POST start outcomes require review, not blind retries. Standard input/output fields were checked against the public Actor README/input documentation (`https://apify.com/apify/instagram-search-scraper/input-schema`); no paid Actor was called. Live mode is unavailable. Offline mocked tests do not certify real-world search quality or current pricing; any paid smoke requires separate authorization.


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
