# مدل داده

## Independent Instagram campaigns (2026-10-12)

Instagram now requires an explicitly selected **Instagram campaign**; Places campaigns and Lead exports are unchanged. Create/list campaigns at `/instagram-campaigns`, inspect profiles and run history at `/instagram-campaigns/{campaign_id}`, then select the campaign on `/search?source=instagram`. Empty lists link to campaign creation. Existing Instagram runs remain run-exportable but are **not automatically imported**.

Campaign JSON/CSV downloads use `/instagram-campaigns/{campaign_id}/export?format=json|csv`. Source-specific fields remain `source_id` (provider ID), `username`, `full_name` (display name), `source_url` (canonical profile URL), `biography`, `external_links`, and existing optional fields. Unicode JSON and UTF-8 BOM CSV preserve Persian; CSV cells mitigate spreadsheet formulas, including leading whitespace. Only validated public profiles and safe HTTP(S) links are retained; business status remains optional and is not verified business evidence. No contacts are inferred from biography.

CLI examples: `instagram-campaign create "کافه‌ها" --campaign cafes`, `instagram-campaign list`, `instagram-search "کافه تهران" --campaign cafes`, `jobs submit-instagram "کافه تهران" --campaign cafes --idempotency-key KEY`, `instagram-campaign export cafes profiles.csv --format csv`. Existing `instagram-export RUN_ID OUTPUT` remains available. APIs: `GET/POST /api/instagram-campaigns`; `POST /api/jobs` includes `source=instagram`, `search`, `searchLimit`, `campaign_id`, and `idempotency_key`. Missing or Places-only selections are rejected before provider execution.

SQLite migration **18** adds separate campaign/run/profile-observation tables without moving historical data. Run payloads and observations commit atomically; replayed successful run IDs are immutable and cannot switch campaigns. Aggregation prefers stable provider IDs, falls back to case-insensitive canonical usernames, and selects the latest valid observation by `(started_at, run_id)` descending. Renamed stable IDs stay one profile; distinct IDs sharing a reused username remain distinct. Failed/empty runs remain in history and never erase prior profiles. Instagram cache identity is campaign-specific and versioned independently from historical run storage.

**Deployment:** stop the owned web server and worker together before migration; restart them with this code against the same database. Migration runs at initialization. The implementation/tests did not open or migrate the live database, restart running sessions, or call paid Actors. Do not roll back to a schema-17 binary after migrating.


## Current release boundary (2026-10-11)

Only Google Places and independent Instagram Search are executable. Instagram is standard-only (`liveSearch=false`, enhancement=false), one comma-free phrase, default 10 and limit 1..250. Requests, profiles, reload and exports are source-specific; no contact extraction or geographic guarantee. Existing SQLite/history are preserved. Any references below to Google Search, LinkedIn, YouTube, TikTok or Instagram enrichment are **historical**, not active product capabilities. See [the current integration contract](06-apify-integration.md) and [operations](02-operations-guide.md). No paid smoke or live-mode certification was performed.


مدل مرکزی `Lead` نماینده یک کسب‌وکار محلی است.

## فیلدهای اصلی

- `name`: نام کسب‌وکار
- `address`: آدرس قابل نمایش
- `phone`: شماره کاری
- `website`: وب‌سایت
- `category`: عبارت/دسته جست‌وجو
- `rating`: امتیاز منبع
- `reviews`: تعداد reviews
- `source`: منبع رکورد
- `score`: امتیاز کیفیت داخلی

## Campaign و روابط ذخیره‌سازی

- `leads` هر کسب‌وکار را یک‌بار با کلید تطبیق نگه می‌دارد.
- `campaigns` گروه‌های کاری را نگه می‌دارد؛ `general` Campaign پیش‌فرض است.
- `campaign_leads` عضویت چندبه‌چند لید و Campaign را ثبت می‌کند.
- `runs.campaign_id` مشخص می‌کند هر اجرای جست‌وجو متعلق به کدام Campaign است.

یک لید مشترک می‌تواند در چند Campaign دیده شود، بدون اینکه ردیف اصلی آن در `leads` تکثیر شود. عضویت Campaign نخستین و آخرین زمان مشاهده را ثبت می‌کند. خروجی Campaign از آخرین وضعیت Lead می‌آید؛ نسخهٔ تاریخی از فیلدهای Lead در این فاز ساخته نمی‌شود.

## Normalization

نام، فاصله‌ها، URL و مقادیر خالی پیش از ذخیره normalize می‌شوند. رکوردهای یکسان باید با upsert از تکثیر غیرضروری جلوگیری کنند. ماژول `src/quality/normalization.py` کلید canonical را بدون تغییر مقدار نمایشی تولید می‌کند و حروف عربی/فارسی را فقط برای جست‌وجوی هویت همسان می‌سازد.

## Schema version 3: identity و provenance

هر Lead اکنون یک `lead_id` پایدار مستقل از تغییر نام، آدرس یا تلفن دارد. جدول append-only `observations` منبع، source record ID، Run، زمان گردآوری و فیلدهای مشاهده‌شده را نگه می‌دارد و `field_evidence` شواهد هر فیلد را ثبت می‌کند. migration نسخهٔ ۳ برای دیتابیس تازه و legacy idempotent است و در failure rollback می‌شود.

در schema v17، `campaign_leads` به کلید اصلی `(campaign_id, lead_id)` مهاجرت کرده و `lead_dedup_key` از membership حذف شده است؛ upsert می‌تواند کلید dedup را بدون بازنویسی عضویت تغییر دهد. `lead_id` در upsert با source/source_id ثابت می‌ماند، حتی اگر تلفن یا فیلدهای mutable تغییر کند.

## کیفیت و provenance

matching محافظه‌کارانه است: source ID یکسان merge، domain+address یکسان merge، شعبه‌های متفاوت separate و شواهد ضعیف review می‌شوند. نبود evidence به‌معنای false بودن داده نیست و confidence ناشناخته باید ناشناخته بماند. داده‌ای که صرفاً از تشابه نام به دست آمده، مالکیت قطعی محسوب نمی‌شود.

`src/quality/metrics.py` completeness را جدا از score قدیمی محاسبه می‌کند. export CLI فیلترهای اختیاری `--min-completeness`، `--has-phone` و `--has-website` دارد؛ بدون این flags قرارداد JSON/CSV قبلی تغییر نمی‌کند. جدول `lead_merge_audit` دلیل، confidence، زمان و snapshot رکورد ادغام‌شده را نگه می‌دارد تا merge قابل audit و undo باشد.

## مشاهدات پلتفرمی مستقل

`PlatformObservation` در `src/results.py` برای نتایج اختیاری و مستقل Instagram، YouTube و TikTok استفاده می‌شود. فیلدهای مشترک کسب‌وکار (`name`، توضیح، location، website و phone) کنار `metadata` مخصوص پلتفرم و `contact_links` نگه‌داری می‌شوند؛ بنابراین فعال‌سازی یا شکست یک جست‌وجوی پلتفرمی، نتیجه Places را تغییر نمی‌دهد. Connectorهای اجتماعی فعلاً disabled-by-default هستند و هیچ Actor پولی اجرا نمی‌شود.

لینک‌های تماس با allowlist قطعی فقط HTTPS و دامنه‌های حرفه‌ای شناخته‌شده (خود پلتفرم، WhatsApp/Telegram) پذیرفته می‌شوند؛ ایمیل، نام مالک و فیلدهای شخصی حذف می‌شوند. URL پروفایل نیز باید به دامنه همان پلتفرم تعلق داشته باشد.

## حریم خصوصی

تنها داده عمومی و حرفه‌ای کسب‌وکار مجاز است. اطلاعات خصوصی افراد، حدس مالکیت و داده حساس نباید ذخیره یا enrich شود.

## کیفیت فیلدها

هر Lead اکنون می‌تواند `field_evidence` و `field_confidence` داشته باشد. Evidence فقط منشأ فنی و حرفه‌ای داده را ثبت می‌کند؛ confidence کیفیت همان فیلد را بین صفر و یک نشان می‌دهد و هرگز به معنی مالکیت فردی نیست. رکوردهای Places و LinkedIn Jobs برای فیلدهای ساختاریافته confidence بالاتری دارند؛ Google Search فقط candidate است.
