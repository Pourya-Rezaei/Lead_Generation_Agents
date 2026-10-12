# تاریخچه تغییرات و وضعیت فعلی پروژه

## به‌روزرسانی index حافظهٔ کد (2026-10-12)

- index محلی CBM با آخرین وضعیت پروژه دوباره ساخته شد.
- وضعیت نهایی: `ready`؛ ۱٬۳۸۹ node و ۵٬۳۸۴ edge؛ `parse_unusable: 0`.
- سه هشدار `parse_partial` در templateهای `templates/base.html`، `templates/job_detail.html` و `templates/search.html` ثبت شد؛ تحلیل این خطوط best-effort است.
- `.env` همچنان طبق policy خارج از index باقی ماند.


## Independent Instagram campaigns (2026-10-12)

Instagram now requires an explicitly selected **Instagram campaign**; Places campaigns and Lead exports are unchanged. Create/list campaigns at `/instagram-campaigns`, inspect profiles and run history at `/instagram-campaigns/{campaign_id}`, then select the campaign on `/search?source=instagram`. Empty lists link to campaign creation. Existing Instagram runs remain run-exportable but are **not automatically imported**.

Campaign JSON/CSV downloads use `/instagram-campaigns/{campaign_id}/export?format=json|csv`. Source-specific fields remain `source_id` (provider ID), `username`, `full_name` (display name), `source_url` (canonical profile URL), `biography`, `external_links`, and existing optional fields. Unicode JSON and UTF-8 BOM CSV preserve Persian; CSV cells mitigate spreadsheet formulas, including leading whitespace. Only validated public profiles and safe HTTP(S) links are retained; business status remains optional and is not verified business evidence. No contacts are inferred from biography.

CLI examples: `instagram-campaign create "کافه‌ها" --campaign cafes`, `instagram-campaign list`, `instagram-search "کافه تهران" --campaign cafes`, `jobs submit-instagram "کافه تهران" --campaign cafes --idempotency-key KEY`, `instagram-campaign export cafes profiles.csv --format csv`. Existing `instagram-export RUN_ID OUTPUT` remains available. APIs: `GET/POST /api/instagram-campaigns`; `POST /api/jobs` includes `source=instagram`, `search`, `searchLimit`, `campaign_id`, and `idempotency_key`. Missing or Places-only selections are rejected before provider execution.

SQLite migration **18** adds separate campaign/run/profile-observation tables without moving historical data. Run payloads and observations commit atomically; replayed successful run IDs are immutable and cannot switch campaigns. Aggregation prefers stable provider IDs, falls back to case-insensitive canonical usernames, and selects the latest valid observation by `(started_at, run_id)` descending. Renamed stable IDs stay one profile; distinct IDs sharing a reused username remain distinct. Failed/empty runs remain in history and never erase prior profiles. Instagram cache identity is campaign-specific and versioned independently from historical run storage.

**Deployment:** stop the owned web server and worker together before migration; restart them with this code against the same database. Migration runs at initialization. The implementation/tests did not open or migrate the live database, restart running sessions, or call paid Actors. Do not roll back to a schema-17 binary after migrating.


Validation: `.venv/bin/python -m pytest -q --basetemp=.test-campaign-work` → **226 passed**, one existing Starlette/httpx deprecation warning; module CLI help smoke and `git diff --check` passed. Focused coverage includes migration-17 upgrade/idempotence/no import, source separation, stable-ID/username aggregation, latest ordering and replay, failed/empty runs, transaction rollback, safe Unicode CSV/JSON, server-side selection, campaign pages/API, CLI and cache references. Existing uncommitted work was preserved; no commits or live database changes.

## 2026-10-11 — Independent two-source release

## Current two-source release (2026-10-11)

The executable product supports only **Google Places** and **independent Instagram Search**. Places retains its query/location/limit contract. Instagram uses `apify~instagram-search-scraper`: exactly one editable `search` phrase (comma-separated terms rejected), `searchLimit` defaults to 10 and accepts 1..250, `searchType=user`, `liveSearch=false`, and `enhanceUserSearchWithFacebookPage=false`. No old `resultsType`, `directUrls`, or `addParentData` is sent.

Select a source at `/search` before its separate form. Instagram jobs contain `source`, `search`, and `searchLimit`, not a fabricated location. Only explicitly public (`private=false`) profiles are accepted. Business status is optional and is not proof of a verified business. Names and canonical links, optional public biography, safe external links and aggregate counts are retained; contacts are not extracted from biography. Posts, comments, audience lists, Facebook data and email enrichment are discarded at ingestion. Geography is not guaranteed; absent address is not an error.

Google Search, LinkedIn Jobs, YouTube, TikTok and the old Instagram enrichment workflow are **historical, non-executable**. Existing database rows are preserved without schema redesign. Old requests cannot start, retry, resume or replay cache; generic job history/provider-attempt information and safe abandonment remain available. The older sections below that discuss these sources describe previous releases, not current capabilities.

Instagram profiles persist in existing run metadata and allowlisted raw records, never as fabricated Leads. Reload/export is scoped to one independent run; campaign Lead exports retain existing Places and historical Lead rows, and do not fabricate Instagram Leads. Historical profile candidates remain read-only. JSON/CSV downloads: `/api/instagram-runs/{run_id}/export/{json|csv}`. CLI: `instagram-search "phrase" --search-limit 10`, `jobs submit-instagram "phrase" --idempotency-key KEY`, and `instagram-export RUN_ID OUTPUT --format json`. API `/api/jobs` accepts a single source-specific request plus `idempotency_key`; multi-source/social/enrichment public routes are removed.

Provider run IDs are journaled before polling; resume uses the same known run. Unknown POST start outcomes require review, not blind retries. Standard input/output fields were checked against the public Actor README/input documentation (`https://apify.com/apify/instagram-search-scraper/input-schema`); no paid Actor was called. Live mode is unavailable. Offline mocked tests do not certify real-world search quality or current pricing; any paid smoke requires separate authorization.

Earlier entries below are historical and preserved verbatim. No database rows were deleted or schema redesign performed. Existing unrelated worktree changes were retained.


## اصلاح خروجی مستقل پیج Instagram (2026-10-11)

- قرارداد عمومی رسمی build `0.0.804` بررسی شد؛ discovery با فقط `apify~instagram-scraper` و `searchType=profile/resultsType=details/searchLimit` اجرا می‌شود. Google Search Actor یا details run دوم اضافه نشده است؛ Actor می‌تواند در داخل خود از Google search استفاده کند.
- خروجی معتبر نام پیج و لینک HTTPS canonical همان پیج دارد؛ نام خالی به username برمی‌گردد. فقط پروفایل صریحاً عمومی و تجاری پذیرفته می‌شود؛ مکان بدون پیج، دادهٔ پست/owner و هویت نامعتبر پیج نیست. شهر فقط keyword است؛ آدرس از قرارداد رسمی فعلی ارائه نمی‌شود و null می‌ماند.
- projection تایپ‌شده، raw allowlist و شمارش دریافت/پذیرش/حذف با دلیل امن در جدول‌های موجود هماهنگ شدند. هیچ migration یا تغییر قرارداد Lead/export انجام نشد؛ پیج‌ها بدون Lead در صفحهٔ همان Job، پس از reload و cache replay نمایش داده می‌شوند. cache قدیمی Instagram با نسخهٔ قرارداد جدید کنار گذاشته شد، بدون تبدیل دادهٔ مکان.
- run ID پیش از polling ثبت و با همان شناسه resume می‌شود؛ start retry کور ندارد. start نامعلوم، rate limit، timeout، خطای dataset و قرارداد ناشناخته ثبت امن دارند؛ timeout محلی توقف Actor یا هزینهٔ قطعی را ثابت نمی‌کند. success خالی با خطای قرارداد متفاوت است.
- اعتبارسنجی Python 3.14: `.venv/bin/python -m pytest -q tests/test_instagram_discovery.py tests/test_instagram_enrichment.py tests/test_web_jobs.py tests/test_search_failures.py` → **115 passed**؛ `.venv/bin/python -m pytest -q` → **323 passed**، هر دو با یک warning موجود Starlette/httpx. `git diff --check` موفق بود. تغییرات قبلی حفظ شدند؛ هیچ سرور/worker process، migration، اجرای پولی یا commit ایجاد نشد. کیفیت/سرعت discovery واقعی و smoke زنده هنوز تأیید نشده‌اند.

## Instagram enrichment آفلاین و مجوز مستقل (2026-10-10)

- adapter `apify~instagram-scraper` در حالت details به profile candidate تأییدشدهٔ Lead موجود وصل شد؛ generic discovery غیرفعال و TikTok با انتخاب کاربر blocked باقی است؛ LinkedIn تغییر نکرد.
- کاربر دریافت extra content از Actor را فقط با حذف فوری مجاز کرد؛ scalar allowlist پیش از storage/observation/cache/UI/export اعمال می‌شود. posts/comments/follower lists/metrics/extra fields نگهداری یا نمایش نمی‌شوند.
- worker/job، resume و ambiguity review، abort/cancellation race، budget reservation و lineage موجود reuse شدند؛ مجوز environment و per-job پیش‌فرض disabled است. profile review برای ثبت Job و مشاهدهٔ evidence متصل شد.
- schema عمومی رسمی بررسی شد؛ اجرای پولی، live smoke، قیمت قطعی و build certification انجام نشد. بودجهٔ محلی سقف تضمین‌شدهٔ provider نیست. هیچ migration یا تغییر export Lead لازم نبود؛ cache فقط reference نگه می‌دارد و replay enrichment برای revalidation غیرفعال است.
- تست‌های mocked و راهنمای opt-in/rollback اضافه شدند؛ validation با Python 3.14: focused **87 passed** و full **288 passed**؛ هر دو با یک warning موجود Starlette/httpx. هیچ commit ایجاد نشد. رکورد CBM قبلی زیر بدون تغییر حفظ شد.

## به‌روزرسانی index پس از پیاده‌سازی‌های جدید (2026-10-10)

- index محلی CBM با کدهای تازه پیاده‌سازی‌شده دوباره ساخته شد.
- وضعیت نهایی: `ready`؛ ۱٬۳۵۶ node و ۵٬۴۶۹ edge؛ `parse_unusable: 0`.
- هشدار `parse_partial` برای `templates/search.html` در خطوط ۱۱ و ۱۹ همچنان باقی است.
- `.env`، دیتابیس‌ها و دادهٔ validation محلی طبق policy خارج از index باقی ماندند.


## اجرای CI خودکار روی push (2026-10-10)

- workflow گیت‌هاب در `.github/workflows/tests.yml` اکنون فقط با رویداد `push` اجرا می‌شود و برای `pull_request` فعال نیست.
- ماتریس تست Python 3.10 تا 3.14، نصب editable پروژه با وابستگی‌های تست و اجرای `pytest -q` حفظ شد.
- اعتبارسنجی محلی معادل CI با Python 3.14 موفق بود: `216 passed, 1 warning`.

## به‌روزرسانی مجدد index حافظهٔ کد (2026-10-10)

- index محلی CBM با آخرین کدها و تغییرات پروژه دوباره ساخته شد.
- وضعیت نهایی: `ready`؛ ۱٬۲۸۱ node و ۵٬۲۶۵ edge؛ `parse_unusable: 0`.
- هشدار `parse_partial` برای `templates/search.html` در خطوط ۱۱ و ۱۹ همچنان باقی است.
- `.env` و دیتابیس محلی طبق policy خارج از index باقی ماندند.

## رفع یافته‌های قابلیت اتکا و همگام‌سازی وضعیت (2026-10-10)

- شروع Actor از retry عمومی جدا شد؛ timeout/قطع ارتباط/5xx یا پاسخ موفق نامعتبر به‌عنوان نتیجهٔ نامعلوم ثبت می‌شود و Job به `needs_review` می‌رود، در حالی که GETهای قابل retry رفتار قبلی را حفظ می‌کنند.
- وضعیت `SearchResult` در handler به worker منتقل می‌شود؛ شکست/abort/timeout دیگر به موفقیت پیش‌فرض تبدیل نمی‌شود.
- cancellation پس از ثبت run ID دوباره بررسی و به‌صورت اتمیک claim می‌شود تا درخواست abort تکراری نشود؛ شکست نامعلوم abort به `needs_review` می‌رود و abort هنگام لغو به `cancelled` ختم می‌شود.
- فیلد `reviews` از raw Places و mapping لید حذف شد؛ فقط `reviewsCount` aggregate حفظ می‌شود. تجمیع چندمنبعی اکنون `partial` را مستقل از موفقیت کامل حفظ می‌کند.
- roadmap، راهنمای شناخت پروژه و مستند Apify با وضعیت فعلی منابع، worker، lifecycle، حریم خصوصی و تست‌ها همگام شدند.
- suite کامل Python 3.14: `216 passed, 1 warning`؛ warning deprecation مربوط به Starlette/httpx است. ماتریس قبلی Python 3.10–3.14 با 197 تست در هر نسخه مربوط به پیش از این اصلاحات است؛ اجرای remote CI هنوز تأیید نشده است. تست‌ها با mock اجرا شدند و Actor پولی فراخوانی نشد.

## تکمیل lifecycle و lineage پایدار (2026-10-10)

- schema به نسخهٔ 17 رسید: campaign membership اکنون فقط `(campaign_id, lead_id)` دارد و provider attempts هویت run/dataset، وضعیت، checkpoint و cancellation را پایدار نگه می‌دارند.
- Connectorها start بدون انتظار طولانی انجام می‌دهند؛ run ID بلافاصله persist می‌شود، resume از همان run صورت می‌گیرد، و abort واقعی از cancellation API فراخوانی می‌شود. crash در نامعلوم بودن پاسخ start به `needs_review` می‌رسد.
- Cache refs شامل observation و raw-record references شده و replay وجود همهٔ lineage را پیش از موفقیت بررسی می‌کند؛ retention وابستگی‌های cache فعال و observation را حفظ می‌کند.
- تست‌های process-level چند worker و بازیابی crash افزوده شدند؛ import ماژول اپلیکیشن دیگر دیتابیس را به‌صورت eager نمی‌سازد.
- roadmap، مدل داده، راهنمای عملیات و مستندات Apify با رفتار جدید همگام شدند. اجرای کامل محلی روی Python 3.10 تا 3.14 در هر نسخه `197 passed` داشت؛ اجرای remote در GitHub Actions هنوز نیازمند remote repository است. هیچ Actor پولی برای این بررسی اجرا نشده است.

## اصلاح مالکیت Job، وضعیت اجرا و هویت LinkedIn (2026-10-10)

- claim صف با `BEGIN IMMEDIATE`، بررسی `rowcount` و commit پیش از اجرای handler اتمیک شد؛ fencing و mutationهای provider/progress نیز از مالکیت معتبر دفاع می‌کنند.
- orchestration اکنون status واقعی `SearchResult` را مصرف می‌کند و اجرای pending/running را موفقیت کاذب گزارش نمی‌کند؛ worker برای نتایج غیرترمینال دوباره queued می‌شود.
- cache فقط نتیجهٔ موفق و mapper version منطبق را می‌پذیرد؛ هزینه‌ها با micro-unit ذخیره می‌شوند تا مبالغ زیر یک سنت صفر نشوند.
- در LinkedIn Jobs، location آگهی دیگر به‌عنوان آدرس دقیق شرکت ذخیره نمی‌شود؛ فقط `companyAddress` معتبر می‌تواند address باشد و evidence/confidence برای فیلد غایب تولید نمی‌شود.
- CLI worker اکنون همان DB درخواست را به service متصل می‌کند و برای jobs چندمنبعی dispatcher مشترک را به‌کار می‌برد؛ idempotency key با payload متفاوت رد می‌شود.
- importهای زمان به `timezone.utc` منتقل شدند تا شرط Python `>=3.10` با کد واقعی سازگار بماند.
- Google Search و LinkedIn Jobs از iterator صفحه‌ای dataset استفاده می‌کنند و فقط در clientهای قدیمی به مسیر legacy fallback دارند؛ بنابراین limit قبل از جمع‌آوری کامل اعمال می‌شود.
- reservation و reconciliation بودجه داخل transaction `BEGIN IMMEDIATE` انجام می‌شوند تا چند worker محلی نتوانند هم‌زمان از quota عبور کنند.
- cache summary بدون reference به `lead_ids` دیگر باعث success کاذب نمی‌شود؛ فقط cacheهای قابل replay که به دادهٔ پایدار اشاره دارند مجاز به cache hit هستند.
- schema به نسخهٔ 11 رسید و cache علاوه بر mapper، `policy_version` را نیز اعتبارسنجی می‌کند تا تغییر policy باعث replay دادهٔ قدیمی نشود.
- `UpsertSummary` اکنون `lead_ids` واقعی را برمی‌گرداند؛ service آن‌ها را همراه run/campaign در `persisted_refs` به worker و cache منتقل می‌کند، بنابراین cache hit قابل replay به persistence متصل است.
- cache replay اکنون پیش از success، وجود campaign، run ترمینال موفق/partial و همهٔ leadهای referenced را بررسی و membership همان campaign را به‌صورت idempotent بازسازی می‌کند؛ cache orphan یا بدون lineage به handler fallback می‌شود.
- schema به نسخهٔ 12 رسید و جدول `lead_identities` برای lookup ایندکس‌شدهٔ `(source, source_id)` اضافه شد؛ upsert دیگر برای source identity به full-table scan وابسته نیست.
- schema به نسخهٔ 13 رسید و `campaign_leads.lead_id` به‌صورت additive اضافه و برای رکوردهای قدیمی backfill شد؛ membershipهای جدید از این پس هم dedup legacy و هم `lead_id` پایدار را نگه می‌دارند.
- schema به نسخهٔ 14 رسید؛ merge و undo اکنون transaction اتمیک دارند، membershipهای هم‌پوشان را بدون خطای uniqueness ادغام می‌کنند و snapshot دقیق campaign membership را برای undo نگه می‌دارند.
- provider run ID در handler از نتیجهٔ همان invocation خوانده می‌شود، نه state mutable مشترک service.
- helperهای backup/restore SQLite با `integrity_check` و `foreign_key_check` اضافه شدند و مسیرهای static/template وب به ریشهٔ پروژه مستقل از cwd متصل شدند.
- schema به نسخهٔ 15 رسید و worker heartbeat در SQLite ثبت می‌شود؛ readiness زمان آخرین heartbeat معتبر را گزارش می‌کند.
- عملیات maintenance محدود و dry-run برای cache منقضی و raw records قدیمی اضافه شد.
- workflow تست CI با matrix نسخه‌های Python 3.10 تا 3.14 اضافه شد.
- connectorهای Apify متد abort مشترک دارند و service می‌تواند run موجود را از طریق endpoint رسمی abort کند؛ resume قبلی همچنان از `search_existing_run` استفاده می‌کند.
- maintenance برای purge runهای قدیمی فقط وقتی مجاز است که raw lineage وابسته نداشته باشند؛ retention با dry-run انجام می‌شود.
- تست‌های اجرای Job، بودجه، orchestration، recovery و connector اجرا شدند؛ هیچ Actor پولی در این تغییرات فراخوانی نشد.


## به‌روزرسانی index حافظهٔ کد (2026-10-10)

- index پایدار CBM پس از اضافه‌شدن تغییرات جدید پروژه دوباره ساخته شد.
- وضعیت: `ready`؛ ۱٬۰۹۲ node و ۴٬۴۲۶ edge؛ `parse_unusable: 0`.
- یک هشدار `parse_partial` برای `templates/search.html` در خطوط ۱۱ و ۱۹ ثبت شد؛ تحلیل template در این خطوط best-effort است.
- `.env` و دیتابیس محلی همچنان خارج از index هستند؛ artifact در `.codebase-memory/` قرار دارد و طبق policy نباید commit شود.

## تکمیل فاز E: دروازه قرارداد Actorهای اجتماعی (2026-10-10)

- metadata صفحات رسمی Apify Store و خلاصه قیمت Instagram، TikTok و YouTube ثبت شد.
- وضعیت schema ورودی هر سه Actor صریحاً `unverified` باقی ماند؛ هیچ Actor پولی فعال نشد.
- مدل `ContractGateReport` اضافه شد و فعال‌سازی را به عبور هم‌زمان schema، privacy و pricing گره می‌زند.
- تست‌های آفلاین تضمین می‌کنند شکست هر دروازه وضعیت را blocked نگه می‌دارد.
- هیچ اجرای زنده یا token جدیدی استفاده نشد.


این سند خلاصه‌ای از کارهای انجام‌شده در مرحله تثبیت پروژه را ثبت می‌کند تا تصمیم‌های فنی، تغییرات معماری و معیارهای اعتبارسنجی برای ایجنت یا توسعه‌دهنده بعدی قابل پیگیری باشد.

## قابلیت انتخاب چندمنبع (2026-10-09)

- descriptorهای capability برای منابع Places، Google Search و منابع اجتماعی/وب اضافه شد.
- API افزایشی `source_capabilities()` و `select_sources()` بدون تغییر مسیر قدیمی `search(source=...)` اضافه شد.
- انتخاب چندمنبع اتمیک اعتبارسنجی می‌شود؛ منابع غیرفعال پیش از ساخت Connector خطای امن می‌دهند و Actor اجتماعی فعال نمی‌شود.
- تست‌های selection آفلاین و بدون Actor پولی اضافه شد.

## دامنه کار انجام‌شده

- ممیزی کامل ساختار، کد، تست‌ها، مستندات، امنیت، حریم خصوصی و کارایی.
- طراحی برنامه اصلاح مرحله‌ای به‌جای بازنویسی کامل.
- افزودن Git و ایجاد branch اصلی `main`.
- ایجاد اولین commit پروژه با پیام `chore: initialize project version control`.
- اجرای تست‌های آفلاین و بدون درخواست واقعی به Apify.
- نصب local ابزار `codebase-memory-mcp` در `.tools/` و ایجاد راهنمای عملیاتی برای Agentها.

## تغییرات معماری

### Apify

- ایجاد Client واحد در `src/apify.py`.
- ارسال credential فقط با Header احراز هویت؛ token در URL یا پیام خطا قرار نمی‌گیرد.
- طبقه‌بندی خطاهای credential، endpoint، timeout، خطاهای موقت و پاسخ malformed.
- retry محدود و قابل‌تزریق با backoff.

### قرارداد Connector

- ایجاد `RunStatus` و `SearchResult` در `src/results.py`.
- Connectorها علاوه بر لید، وضعیت اجرا، شناسه run/dataset، هشدار، زمان اجرا و raw record محدودشده را برمی‌گردانند.
- Places statusهای واقعی را بررسی می‌کند و اجرای ناقص را موفق گزارش نمی‌کند.
- داده خام با allowlist ذخیره می‌شود.

### مدل داده

- validation نام، rating، review count و URL.
- normalization فاصله، کاراکترهای نامرئی، شماره‌های فارسی و URL.
- افزودن provenance اختیاری مثل source ID و source URL.
- تفکیک completeness و popularity از score سازگار قدیمی.
- dedup بر اساس source ID، تلفن، دامنه و سپس شواهد آدرس/نام.

### Storage و migration

- migration نسخه‌دار، idempotent و transaction-based در `src/migrations.py`.
- repositoryهای جدا برای leads، runs و raw records.
- حفظ facade قدیمی `LeadStore` برای سازگاری.
- ساخت خودکار parent directory دیتابیس.
- ثبت lifecycle اجرا و امکان purge رکوردهای خام.
- migration روی کپی دیتابیس قدیمی آزمایش شد و ۲۰ رکورد حفظ شدند.

### Service و CLI

- انتقال orchestration به `SearchLeadsService`.
- انتخاب Connector از طریق `ConnectorRegistry`.
- CLI فقط validation، اجرای use case و نمایش خلاصه را انجام می‌دهد.
- منبع `web` فعلاً feature-disabled است و درخواست شبکه ارسال نمی‌کند.

### Export

- حفظ قرارداد پیش‌فرض JSON/CSV.
- حالت extended برای provenance.
- export iterator-based برای مصرف حافظه کمتر.
- محافظت CSV در برابر formula injection.
- پشتیبانی از مسیرهای تو در تو و خروجی خالی با header پایدار.

## امنیت و حریم خصوصی

- `.env`، دیتابیس محلی، محیط مجازی و cacheها در `.gitignore` قرار گرفتند.
- token واقعی در source، URL، test fixture یا commit قرار نگرفت.
- raw payload با allowlist محدود می‌شود.
- جمع‌آوری reviewer/person و استنتاج مالکیت خارج از محدوده است.
- تست‌ها از token واقعی و API پولی استفاده نمی‌کنند.

## تست و اعتبارسنجی نهایی

آخرین اعتبارسنجی آفلاین:

```text
pytest -q          -> 89 passed
CLI --help         -> successful
Web smoke routes   -> /, /campaigns, /search و /static/styles.css موفق
```

هشدار deprecation مربوط به ترکیب Starlette TestClient و httpx مانع اجرای تست‌ها نیست.

هیچ اجرای زنده‌ای علیه Apify در این مرحله انجام نشد.

## فاز A: هویت پایدار و provenance

- schema به نسخهٔ ۳ ارتقا یافت و برای Leadها `lead_id` پایدار اضافه شد.
- جدول‌های `observations` و `field_evidence` برای ثبت منبع، زمان، source record و evidence ایجاد شدند.
- upsert با source/source_id ثابت، هویت Lead را هنگام تغییر فیلدهای mutable حفظ می‌کند.
- normalization canonical و matching محافظه‌کارانه برای شعبه‌ها و شواهد ضعیف اضافه شد.
- migration روی دیتابیس تازه و legacy idempotent و transaction-safe است.
- baseline تست از 89 به `93 passed` رسید.
- `campaign_leads` هنوز برای سازگاری از dedup key استفاده می‌کند؛ انتقال کامل به lead_id در migration جداگانه باقی مانده است.

## رابط وب فارسی و RTL

- FastAPI، Jinja2 و `python-multipart` به وابستگی‌های runtime اضافه شدند.
- پنل محلی در `src/web/` شامل Dashboard، Campaign، جست‌وجوی synchronous Places و export JSON/CSV است.
- templateهای فارسی با `lang="fa"` و `dir="rtl"` و stylesheet مستقل responsive در `static/styles.css` اضافه شدند.
- پنل فقط روی localhost در نظر گرفته شده و هنوز احراز هویت، چندکاربره‌بودن و queue ندارد.
- تست‌های Web UI و export به suite اضافه شدند و baseline فعلی به `89 passed` رسید.

## Codebase Memory

- index کامل پس از تغییرات UI refresh شد: `668 nodes` و `2233 edges`، با `parse_unusable: 0`.
- parse جزئی template جست‌وجو به syntax Jinja مربوط است و خطای runtime محسوب نمی‌شود.
- `.env`، دیتابیس محلی و cacheها عمداً خارج از index/commit نگه داشته می‌شوند.

## فازهای جدید: قرارداد اجتماعی و orchestration چندمنبعی

- capability registry و انتخاب منبع به‌صورت مستقل برای Places، Google Search و Actorهای اجتماعی اضافه شد.
- قراردادهای privacy-scoped برای Instagram، TikTok و YouTube ثبت شد؛ این Actorهای پولی تا تأیید schema، privacy و pricing غیرفعال باقی می‌مانند.
- UI فارسی جست‌وجو اکنون منابع را نمایش می‌دهد و منابع غیرفعال را قفل می‌کند.
- `MultiSourceOrchestrator` منابع فعال را مستقل اجرا می‌کند، نتایج موفق را هنگام شکست منبع دیگر حفظ می‌کند و وضعیت `succeeded`، `partial` یا `failed` می‌دهد.
- API `POST /api/orchestrated-searches` با idempotency و اعتبارسنجی capability اضافه شد؛ Worker نیز وضعیت partial را حفظ می‌کند.
- پنل وب مسیرهای `/jobs` و `/jobs/{job_id}` را برای مشاهدهٔ تاریخچه و جزئیات Job ارائه می‌کند.
- صفحهٔ Job با polling خودکار progress، وضعیت هر منبع و اجرای مجدد Jobهای `failed`، `partial` و `cancelled` تکمیل شد.
- صفحهٔ `/profiles/{lead_id}` برای بازبینی و تأیید/رد دستی پروفایل‌های عمومی اضافه شد.
- وضعیت contract gate و سیاست عدم اجرای Actorهای پولی اجتماعی در `/sources` و `/api/source-contracts` قابل مشاهده شد.
- درخواست فعال‌سازی هر Actor نیز تا عبور schema/privacy/pricing gate با خطای امن `409` رد می‌شود.
- آخرین اعتبارسنجی آفلاین: `pytest -q` با نتیجهٔ `167 passed` و یک warning سازگاری Starlette/httpx.

## تصمیم‌های باقی‌مانده برای توسعه آینده

- افزودن Connector جدید فقط پس از تعریف source contract، provenance و privacy review.
- اجرای واقعی Actorهای اجتماعی فقط پس از تأیید schema دقیق و smoke test پولی با رضایت صریح.
- طراحی queue یا اجرای async فقط بعد از اثبات نیاز عملیاتی.
- افزودن CI پس از اتصال repository به remote.
- تعیین سیاست retention مطابق نیاز واقعی کسب‌وکار و قوانین محل اجرا.
- ایجاد migration جدید به‌صورت ترتیبی و بدون شکستن JSON/CSV پیش‌فرض.

## فاز A: مشاهدات پلتفرمی مستقل

- قرارداد backward-compatible `PlatformObservation` و `PlatformSearchResult` برای نتایج مستقل اجتماعی اضافه شد؛ فیلدهای مشترک با metadata و contact links مخصوص پلتفرم تفکیک شده‌اند.
- normalization و allowlist قطعی برای URL پروفایل و لینک‌های تماس حرفه‌ای عمومی Instagram، YouTube و TikTok اضافه شد.
- Connectorهای اجتماعی و Actorهای پولی همچنان disabled-by-default هستند و در این تغییر هیچ اجرای شبکه‌ای فعال نشده است.

## وضعیت فعلی پس از Campaign و ثبت خطا

- Campaignها با جدول‌های `campaigns` و `campaign_leads` اضافه شدند.
- Runها به Campaign متصل هستند و Leadها می‌توانند عضو چند Campaign باشند.
- export می‌تواند سراسری یا با `--campaign ID` محدود باشد.
- خطاهای اجرای جست‌وجو به‌عنوان Run با status `failed` ثبت می‌شوند؛ خطای اصلی همچنان به CLI برمی‌گردد.
- برای failureهایی که پیش از دریافت شناسهٔ Apify رخ می‌دهند، `local-<uuid>` به‌عنوان شناسهٔ داخلی استفاده می‌شود.
- شناسهٔ Provider در صورت وجود فقط به‌صورت metadata امن نگه‌داری می‌شود.
- تست‌های regression مربوط به failure handling اضافه شده و کل suite به `79 passed` رسیده است.
- پوشهٔ worktree موقت حذف شده و checkout اصلی مسیر رسمی توسعه است.

## کارهای باقی‌مانده

- تکمیل deduplication چندمنبعی و normalization قابل مشاهده
- provenance/evidence و confidence دقیق‌تر برای داده‌های تکمیلی
- افزودن فیلترهای quality/score به export
- سپس افزودن Google Search و Connectorهای اجتماعی با privacy review
- در مراحل بعد queue، cache، history مقایسهٔ Runها، CRM export و budget guard

## نمودار معماری MVP

- نمودار Mermaid جریان کامل CLI تا Apify، mapping، normalization/scoring، تراکنش SQLite و exportهای JSON/CSV را در `docs/04-architecture.md` ثبت می‌کند.
- مسیر ثبت Run ناموفق، عدم ذخیره Lead/raw برای failure و مرز حریم خصوصی داده‌های عمومی و حرفه‌ای نیز در نمودار و توضیحات معماری مشخص شده است.
- این تغییر مستنداتی است و قرارداد CLI، schema و رفتار اجرایی را تغییر نمی‌دهد.

## وضعیت Git

- branch اصلی: `main`
- آخرین commitهای مرتبط: `e5ffd4b` برای Campaignها، `57f6612` برای ثبت failureها، `669c84d` برای ایزوله‌کردن regression test از `.env`
- فایل‌های حساس مانند `.env` در commit وارد نشده‌اند.

## به‌روزرسانی نمودار معماری اجرایی (2026-10-10)

- `docs/04-architecture.md` با وضعیت واقعی CBM و source code همگام شد: ۱٬۰۹۲ node، ۴٬۴۲۶ edge و `parse_unusable: 0`.
- مسیرهای Job/Worker، idempotency، lease/fencing، retry/cancel، cache و budget reservation به نمودار اضافه شدند.
- انتخاب چندمنبعی و نتیجهٔ partial، Google Search و enrichment پروفایل عمومی، evidence-based review و contract gate منابع اجتماعی مستند شدند.
- مرزهای privacy، allowlist raw، failure persistence و محدودیت‌های Web UI محلی صریح‌تر شدند.
- این تغییر فقط مستنداتی است و قرارداد اجرایی یا schema را تغییر نمی‌دهد.
- syntax نمودار برای سازگاری با rendererهای Mermaid ساده‌سازی شد: labelها quote شدند، شکست خط به `<br/>` تبدیل شد و brace/edge-labelهای حساس حذف شدند.

## Production hardening (2026-10-10)

- Recovery برای leaseهای منقضی‌شده و حفاظت fencing حفظ شد.
- `JobWorker.stop()` برای shutdown هماهنگ اضافه شد.
- endpointهای `/health/live` و `/health/ready` با خطاهای sanitized اضافه شدند.


## Explainable data quality (2026-10-10)

- `Lead` اکنون evidence و confidence سطح فیلد را به‌صورت backward-compatible نگه می‌دارد.
- connectorهای Places، Google Search و LinkedIn Jobs provenance و confidence منبع‌محور ثبت می‌کنند.
- دلیل‌های deterministic برای deduplication اضافه شد؛ هیچ owner inference انجام نمی‌شود.
