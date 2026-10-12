# راهنمای عملیات

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


## اجرای معمول

1. محیط مجازی را فعال کنید.
2. وجود `APIFY_API_TOKEN` را بررسی کنید.
3. جست‌وجو را با `--limit` کنترل‌شده اجرا کنید.
4. خروجی را در `exports/` ذخیره کنید.
5. SQLite و خروجی‌ها را backup کنید.

## صف اجرای محلی

در فاز B، جدول `jobs` primitive صف محلی را فراهم می‌کند: ارسال تکراری با `idempotency_key` همان Job را برمی‌گرداند، Jobهای queued قابل claim توسط یک worker هستند و lease/fencing برای recovery اولیه ثبت می‌شود. handler مربوط به Places اکنون request را به `SearchLeadsService` متصل می‌کند؛ اگر request شامل `estimated_cost` و `max_cost` باشد، worker پیش از اجرا رزرو اتمیک می‌گیرد. Attemptهای provider شامل run/dataset، وضعیت و checkpoint در SQLite ثبت می‌شوند؛ runهای شناخته‌شده resume یا abort می‌شوند و پنجرهٔ نامشخص start به `needs_review` می‌رسد. Jobها هنوز باید با یک worker process مدیریت‌شده اجرا شوند؛ CI matrix پایتون نیز تا اجرای workflow در GitHub remote تأیید نهایی نمی‌شود.

## Instagram enrichment: separate operational opt-in

Offline implementation does **not** authorize a paid run. Keep `INSTAGRAM_ENRICHMENT_AUTHORIZED=false` (default) until an operator separately approves the specific public business profile and current Actor pricing/budget. TikTok remains blocked. The same environment opt-in also makes independent Instagram **profile** discovery selectable; a web search queues a Job, and `/jobs/{job_id}` displays that run's page names/links without requiring Leads. City is only a keyword and profile addresses remain null. Only the Instagram Actor is started; no additional details or Google Search Actor runs are scheduled. Do not enable it before separately approving discovery scope and cost. Successful zero-page results and contract errors are distinct; a local polling timeout does not prove remote termination. Legacy place-result caches are excluded by the new Instagram contract key.

After that separate approval only:

1. Review the existing business candidate in `/profiles/{lead_id}` and explicitly confirm its business relationship; ensure the lead belongs to the chosen campaign.
2. Set `INSTAGRAM_ENRICHMENT_AUTHORIZED=true` for both web and worker processes. Restart them so the setting is effective; token remains environment-only.
3. The profile-review form requires a confirmed Instagram candidate, campaign, USD estimated cost/local maximum, pricing reference, and a per-job execution authorization checkbox. It queues one profile; it does not execute an Actor in the web request.
4. The equivalent API is `POST /api/profile-candidates/{candidate_id}/instagram-enrichment` with `campaign_id`, `execution_authorized: true`, string `estimated_cost`, string `max_cost`, `currency: "USD"`, `pricing_version`, and `idempotency_key`. Unknown fields are rejected. `GET /api/instagram-enrichment/capability` reports readiness without network calls.
5. Process with the existing `leadgen worker --once --db ...` or managed worker. Inspect `/jobs/{job_id}` and profile evidence. Budgets are local admission controls, not provider spending guarantees; actual-cost reservations remain unknown.
6. Cancel via the existing Job API or CLI; abort uses the known provider run even after execution authorization is disabled. In `needs_review`, verify the provider outcome manually: attach a known run with source `instagram_enrichment`, abandon, or retry **only after confirming no remote run exists**. Known-run retries resume, not paid restart.

Rollback: disable the setting in web and worker, restart both, cancel queued/running jobs and verify provider abortion. Disabling does not itself abort active provider runs; ambiguity stays reviewable. Confirmation revoked during execution prevents evidence persistence. Local retention/backup policies still apply to allowlisted business evidence. Actor extra posts/comments/metrics may be received transiently, but must never be retained/exposed. A live operational smoke remains separately blocked pending approval; this implementation was validated only with mocks.

## اجرای پنل وب محلی

```bash
uvicorn src.web.app:app --host 127.0.0.1 --port 8000
```

پنل در <http://127.0.0.1:8000> باز می‌شود. برای توقف سرور `Ctrl+C` بزنید. bind پیش‌فرض فقط localhost است؛ برای دسترسی شبکه‌ای یا اینترنتی این نسخه را تغییر ندهید.

## اجرای جداگانه

```bash
leadgen search "رستوران" "شیراز" --source places --db data/shiraz.db
leadgen export data/shiraz.json --format json --db data/shiraz.db
```

## مدیریت هزینه

- با limit کوچک شروع کنید.
- query دقیق بنویسید.
- شهرهای بزرگ را به منطقه تقسیم کنید.
- Actorهای شبکه‌های اجتماعی را در MVP فعال نکنید.
- runها را در Apify Console بررسی کنید.

## گزارش تست فاز ۲

در تاریخ ۲۰۲۶-۱۰-۰۷، فاز دوم با موفقیت اعتبارسنجی شد:

```text
pytest -q                 -> 4 passed
Places search limit=5    -> Saved 5 leads
JSON export              -> successful
CSV export               -> successful
SQLite database          -> test-phase2.db (48K)
```

فایل‌های آزمون در مسیر `exports/phase2/` تولید شدند. برای تست‌های بعدی از database جداگانه استفاده کنید تا `leads.db` اصلی تغییر نکند.

## مدیریت secret

در صورت افشای token، فوراً آن را در Apify revoke و token جدید ایجاد کنید. `.env` نباید commit شود.

## Production hardening

- `GET /health/live` is a content-free liveness check.
- `GET /health/ready` verifies that the existing SQLite file and required schema tables are readable; it never creates an empty database. It returns `503` with a stable database/schema code when readiness fails. The local web app reports `worker: "not_required"` because CLI workers are separate processes.
- CLI workers renew their SQLite lease through a separate heartbeat connection during long-running handlers; losing the fencing lease prevents stale result persistence.
- The worker recovers expired leases before claiming new work. Fencing tokens prevent stale workers from updating reclaimed jobs.
- `JobWorker.stop()` provides cooperative shutdown and prevents new claims after the stop signal.
- Jobs in `needs_review` are listed with their persisted provider attempts at `GET /api/jobs/{job_id}`. Resolve them with `POST /api/jobs/{job_id}/resolve`: `attach_run` links a run found in the provider console and resumes it; `retry` requires `confirmed_no_remote_run: true` after checking Apify; `abandon` marks the job cancelled. Never choose retry unless the provider console confirms no run was created.
