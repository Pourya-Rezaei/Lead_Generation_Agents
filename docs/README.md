# مستندات Local Lead Generation Agents

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


این پوشه مرجع اصلی شناخت، اجرا، توسعه و نگهداری پروژه است. این پروژه یک برنامهٔ پایتونی محلی برای پیدا کردن لیدهای کسب‌وکار بر اساس **شهر** و **شغل/عبارت جست‌وجو** است؛ از CLI و پنل وب برای منابع منتخب استفاده می‌کند.

## Instagram enrichment آفلاین

تکمیل پروفایل تجاری Instagram برای candidate تأییدشدهٔ Lead موجود به worker و profile review متصل است. discovery مستقل پیج با همان Actor و `searchType=profile/resultsType=details` فقط با `INSTAGRAM_ENRICHMENT_AUTHORIZED=true` قابل انتخاب است؛ پیش‌فرض disabled و TikTok با تصمیم کاربر blocked باقی است. خروجی discovery نام پیج و لینک canonical همان پیج است، مستقل از Lead؛ شهر فیلتر قطعی نیست و آدرس در قرارداد فعلی null است. دادهٔ اضافی Actor در ingestion حذف می‌شود. قرارداد و محدودیت‌ها در [Apify integration](06-apify-integration.md) و opt-in/rollback در [Operations](02-operations-guide.md) توضیح داده شده‌اند. اجرای پولی یا live smoke انجام نشده است.

## وضعیت فعلی

نسخهٔ فعلی برای Google Places، Google Search و اجرای کنترل‌شدهٔ LinkedIn Jobs عملیاتی است:

- ورودی CLI برای query، location، source و limit
- اجرای Actor `compass~crawler-google-places` از طریق Apify
- عدم نیاز به Google Maps API key؛ فقط `APIFY_API_TOKEN` لازم است
- تبدیل dataset به مدل استاندارد Lead و ذخیره در SQLite
- normalization، scoring و upsert پایهٔ لیدها
- مدیریت Campaign با Campaign پیش‌فرض `general`
- اتصال هر Run به Campaign و عضویت چندبه‌چند Leadها در Campaignها
- ذخیرهٔ metadata اجرای Apify و raw recordهای allowlist شده
- ثبت Runهای ناموفق برای خطاهای credential، timeout، شبکه و پاسخ نامعتبر
- جلوگیری از ذخیرهٔ Lead و raw record برای Run شکست‌خورده
- خروجی JSON و CSV سراسری یا محدود به Campaign
- ساخت خودکار پوشهٔ مقصد export
- تست‌های unit و integration کاملاً mock شده‌اند؛ تست‌ها Actor پولی یا token واقعی فراخوانی نمی‌کنند.
- CLI فعال: `search`، `campaign create/list/show` و `export`
- پنل وب محلی فارسی و راست‌به‌چپ با FastAPI/Jinja، CSS responsive و مسیرهای مدیریت Campaign، جست‌وجو و export
- اجرای پنل فقط روی `127.0.0.1`؛ بدون احراز هویت و دسترسی شبکه‌ای در MVP
- orchestration چندمنبعی برای Google Places و Google Search با حفظ نتیجهٔ partial
- نمایش و انتخاب منابع در UI؛ منابع اجتماعی غیرفعال با contract gate باقی می‌مانند
- API idempotent برای ایجاد Job چندمنبعی و handler سازگار با Worker
- تاریخچهٔ اجرا و صفحهٔ جزئیات Job در پنل وب، همراه با لغو/بازیابی Apify و رسیدگی دستی به `needs_review`
- polling خودکار progress، نمایش وضعیت منابع و اجرای مجدد Jobهای شکست‌خورده یا partial
- صفحهٔ بازبینی پروفایل‌های عمومی در `/profiles/{lead_id}`
- صفحهٔ وضعیت منابع و contract gateها در `/sources` و `/api/source-contracts`
- endpoint امن activation request که تا تکمیل schema gate هیچ Actor پولی را فعال نمی‌کند
- وضعیت اعتبارسنجی: `216 passed` روی Python 3.14 پس از اصلاحات؛ ماتریس محلی قبلی `197 passed` در هر نسخهٔ Python 3.10 تا 3.14 داشت و پس از این اصلاحات هنوز دوباره اجرا نشده است. اجرای remote در GitHub Actions نیز هنوز انجام نشده است.

منبع `web` و TikTok فعال نیستند؛ Instagram پیش‌فرض غیرفعال و فقط با مجوز environment مستقل قابل انتخاب است. LinkedIn Jobs برای اجرای کنترل‌شده در کمپین‌ها فعال شده و در رابط وب قابل انتخاب است.
- `ConnectorRegistry.capabilities()` و `SearchLeadsService.source_capabilities()` descriptor قابلیت‌ها را بدون اجرای Actor ارائه می‌کنند؛ `select_sources([...])` انتخاب چند منبع را پیش از ساخت Connector اعتبارسنجی می‌کند و برای منبع غیرفعال خطای امن می‌دهد.

## مسیر مطالعه پیشنهادی

1. [شروع سریع](01-getting-started.md)
2. [راهنمای عملیات](02-operations-guide.md)
3. [مرجع فنی](03-technical-reference.md)
4. [معماری](04-architecture.md)
5. [مدل داده](05-data-model.md)
6. [یکپارچه‌سازی Apify](06-apify-integration.md)
7. [تست و کیفیت](07-testing-and-quality.md)
8. [عیب‌یابی](08-troubleshooting.md)
9. [نقشه راه](09-roadmap.md)
10. [راهنمای تحویل به ایجنت هوش مصنوعی](10-ai-agent-handoff.md)
11. [تاریخچه تغییرات و وضعیت فعلی](11-change-history.md)
12. [راهنمای کار Agent با CBM](12-cbm-agent-guide.md)
13. [راهنمای درک پروژه برای Agent](13-agent-project-understanding.md)

## ساختار کد

- `src/cli.py`: دستورات CLI
- `src/config.py`: تنظیمات Environment
- `src/domain.py`: مدل لید، normalization و scoring
- `src/storage.py`: SQLite و export
- `src/connectors/`: اتصال به منابع داده
- `tests/`: تست‌های پروژه
- `.env`: تنظیمات محلی و secretها؛ هرگز commit نشود

## اصل مهم حریم خصوصی

فقط داده‌های عمومی و حرفه‌ای مرتبط با کسب‌وکار جمع‌آوری شود. سیستم نباید مالکیت شخصی را از روی قرائن حدس بزند یا داده خصوصی جمع کند.
