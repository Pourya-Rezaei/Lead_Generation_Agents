# یکپارچه‌سازی Apify

## Current two-source release (2026-10-11)

The executable product supports only **Google Places** and **independent Instagram Search**. Places retains its query/location/limit contract. Instagram uses `apify~instagram-search-scraper`: exactly one editable `search` phrase (comma-separated terms rejected), `searchLimit` defaults to 10 and accepts 1..250, `searchType=user`, `liveSearch=false`, and `enhanceUserSearchWithFacebookPage=false`. No old `resultsType`, `directUrls`, or `addParentData` is sent.

Select a source at `/search` before its separate form. Instagram jobs contain `source`, `search`, and `searchLimit`, not a fabricated location. Only explicitly public (`private=false`) profiles are accepted. Business status is optional and is not proof of a verified business. Names and canonical links, optional public biography, safe external links and aggregate counts are retained; contacts are not extracted from biography. Posts, comments, audience lists, Facebook data and email enrichment are discarded at ingestion. Geography is not guaranteed; absent address is not an error.

Google Search, LinkedIn Jobs, YouTube, TikTok and the old Instagram enrichment workflow are **historical, non-executable**. Existing database rows are preserved without schema redesign. Old requests cannot start, retry, resume or replay cache; generic job history/provider-attempt information and safe abandonment remain available. The older sections below that discuss these sources describe previous releases, not current capabilities.

Instagram profiles persist in existing run metadata and allowlisted raw records, never as fabricated Leads. Reload/export is scoped to one independent run; campaign Lead exports retain existing Places and historical Lead rows, and do not fabricate Instagram Leads. Historical profile candidates remain read-only. JSON/CSV downloads: `/api/instagram-runs/{run_id}/export/{json|csv}`. CLI: `instagram-search "phrase" --search-limit 10`, `jobs submit-instagram "phrase" --idempotency-key KEY`, and `instagram-export RUN_ID OUTPUT --format json`. API `/api/jobs` accepts a single source-specific request plus `idempotency_key`; multi-source/social/enrichment public routes are removed.

Provider run IDs are journaled before polling; resume uses the same known run. Unknown POST start outcomes require review, not blind retries. Standard input/output fields were checked against the public Actor README/input documentation (`https://apify.com/apify/instagram-search-scraper/input-schema`); no paid Actor was called. Live mode is unavailable. Offline mocked tests do not certify real-world search quality or current pricing; any paid smoke requires separate authorization.


## Instagram discovery contract

The official public build input schema (`https://api.apify.com/v2/acts/apify~instagram-scraper/builds/default`, build **0.0.804**, inspected 2026-10-11) and [Actor README](https://apify.com/apify/instagram-scraper) document `searchType=profile`, `resultsType=details`, `searchLimit` (1–250), and `addParentData=false`. This application caps discovery at 100 and runs **only one Instagram Actor**, searching `query + city`; it does not start the Google Search Actor or a second details run. The Actor itself documents use of Instagram data and Google search internally. City is a keyword, not a verified geographic filter; relevant results are not guaranteed.

Discovery is selectable only when `INSTAGRAM_ENRICHMENT_AUTHORIZED=true`; the default remains disabled. Only explicit `private=false` and `isBusinessAccount=true` profiles are accepted. Unknown privacy/business flags are counted as rejected, not inferred from a name/category. Every accepted result has a validated HTTPS canonical profile link and display name (username fallback). Username-only and URL-only identities are supported; numeric IDs alone, mismatched identities, place/post/reel URLs, private/personal profiles and commenter/owner-derived identities are not page results. The documented profile-details sample has no explicit address field, so `address=null`; no city/bio/place address or phone is inferred. No extra Actor is added to obtain an address.

Provider posts/comments/followers/audience/biography/contact/owner data are discarded immediately. Only `id`, `username`, `url`, `fullName`, `externalUrl`, `businessCategoryName`, `isBusinessAccount`, `private`, `verified` survive the scalar allowlist. Typed Instagram projections and received/accepted/rejected counts plus safe rejection reasons live in the existing run payload, with aligned raw allowlisting; no database migration or business Lead is needed. `/jobs/{job_id}` renders linked page names from that job's run (also after reload/cache replay), never campaign-wide Leads. Legacy place records are not converted and Instagram cache keys use a new contract version.

A known run ID is recorded before polling and resumed without another POST. Start ambiguity requires review; rate-limit/start errors, polling timeout, Actor terminal failure, malformed dataset and retrieval errors are failures rather than successful page discovery. Local timeout does **not** prove Actor cancellation or known final cost. Successful empty/policy-rejected datasets display «تکمیل شد، پیج عمومی تجاری یافت نشد»; unknown/place/post-only schemas fail the contract instead of claiming zero pages. Tests are mocked/offline: no paid calls or live smoke were performed, and real-world discovery quality/latency are unverified.

## Actor فعلی

```text
compass~crawler-google-places
```

این Actor از طریق API آپیفای اجرا می‌شود و به Google Maps API key نیاز ندارد. کلید موردنیاز فقط `APIFY_API_TOKEN` است.

## ورودی

نمونه مفهومی:

```json
{
  "searchStringsArray": ["دندانپزشکی"],
  "locationQuery": "تهران",
  "maxCrawledPlacesPerSearch": 20
}
```

## API flow

Client lifecycle را به عملیات مستقل تقسیم می‌کند: `start_actor`، `get_run`، `wait_for_run`، dataset paging و `abort_run`. کانکتورها ابتدا Actor را بدون انتظار طولانی شروع می‌کنند، run ID را در `provider_attempts` ثبت می‌کنند و سپس همان run را poll می‌کنند. در restart، worker همان run ID را resume می‌کند؛ cancellation از مسیر Job API فراخوانی واقعی abort را انجام می‌دهد. درخواست start یک‌بار ارسال می‌شود و پس از timeout، قطع ارتباط، پاسخ 5xx یا پاسخ موفقِ نامعتبر، نتیجهٔ مبهم به `needs_review` می‌رود تا از start پولی تکراری جلوگیری شود. پاسخ‌های قطعی مانند 401/403 و 404 همچنان به خطای credential/endpoint تبدیل می‌شوند.

رکورد خام Places فقط فیلدهای تجاری allowlist‌شده را نگه می‌دارد. `reviewsCount` می‌تواند به‌عنوان شمارش aggregate در Lead بماند، اما آرایه/متن `reviews` و مشخصات reviewer نه در Lead و نه در raw record ذخیره نمی‌شوند.

1. `POST /v2/acts/compass~crawler-google-places/runs`
2. ارسال Bearer token در Header
3. ثبت پایدار شناسهٔ run پس از پاسخ start
4. poll کردن همان run تا وضعیت terminal
5. خواندن `defaultDatasetId`
6. دریافت صفحات `GET /v2/datasets/{datasetId}/items`
7. mapping رکوردها به `Lead`
8. ثبت observation، raw records و metadata در SQLite
9. در صورت شکست اجرای جست‌وجو، ثبت Run ناموفق در Campaign

توکن نباید در query string قرار گیرد؛ این کار مانع نمایش آن در URL و traceback می‌شود. اجرای موفق، شناسه run، dataset و تعداد رکوردها را در جدول‌های `runs` و `raw_records` ثبت می‌کند.

پس از معتبر بودن ورودی و Campaign، نبودن/رد شدن token، خطای شبکه یا timeout، پاسخ نامعتبر و شکست دریافت dataset نیز به‌عنوان Run ناموفق ثبت می‌شوند. اگر شناسهٔ Apify پیش از شکست دریافت شده باشد، کنار شناسهٔ محلی Run نگه داشته می‌شود؛ اگر شکست پیش از آن باشد، Run فقط شناسهٔ محلی دارد و این به معنی ساخت Run در Apify نیست. پیام خطای اصلی به CLI نمایش داده می‌شود و exit code ناموفق خواهد بود. اطلاعات محرمانه و متن خام exception در شرح ذخیره‌شده قرار نمی‌گیرند.

ثبت failure به دسترس بودن دیتابیس وابسته است. اگر خود دیتابیس در دسترس نباشد یا فرایند ناگهانی متوقف شود، ثبت همان خطا تضمین‌شدنی نیست؛ در این حالت خطای ثبت نیز آشکار گزارش می‌شود و به موفقیت تبدیل نمی‌شود.

## Google Search (فاز C اولیه)

Adapter `google_search` با Actor `apify~google-search-scraper` اضافه شده است. نتیجهٔ Google Search فقط به‌عنوان candidate عمومی با title، URL و description allowlist می‌شود؛ snippet یا شباهت نام، مالکیت یا اطلاعات تماس قطعی محسوب نمی‌شود. اجرای واقعی تا بررسی schema/قیمت Actor و smoke کنترل‌شده باید با limit پایین انجام شود.

## وضعیت پیاده‌سازی فاز ۲

اجرای واقعی با query `دندانپزشکی`، location `تهران` و limit برابر ۵ با موفقیت انجام شد. پنج لید در SQLite ذخیره شد و exportهای JSON و CSV در `exports/phase2/` ساخته شدند. تست‌های خودکار نیز با نتیجه `4 passed` موفق هستند.

## Enrichment وب در فاز C

نتایج Google Search در enrichment فقط به Lead مشخص‌شده با `lead_id` attach می‌شوند و با discovery مستقل کسب‌وکار مخلوط نمی‌شوند. query به‌صورت deterministic از نام کسب‌وکار و شهر ساخته می‌شود. فقط URLهای HTTPS با title و نشانهٔ شهر پذیرفته می‌شوند؛ نتیجهٔ بدون تطبیق شهر یا رکورد malformed حذف و شمارش می‌شود. تطبیق دامنهٔ رسمی موجود، candidate را فقط به `probable` ارتقا می‌دهد؛ directory و snippet هرگز وب‌سایت رسمی یا مالکیت را تأیید نمی‌کنند. crawl مستقیم سایت و email حدسی در این فاز انجام نمی‌شود.

## تطبیق و review پروفایل کسب‌وکار

Candidateهای پروفایل فقط به کسب‌وکار مشخص با `lead_id` وصل می‌شوند. شباهت نام به‌تنهایی هرگز `confirmed` نیست؛ `confirmed` به لینک first-party و شواهد سازگار نیاز دارد. بدون لینک first-party، شواهد حرفه‌ای سازگار حداکثر `probable` می‌شود و تعارض‌ها `unverified` باقی می‌مانند. فقط پلتفرم‌های allowlist و URLهای HTTPS ذخیره می‌شوند و رابطهٔ ثبت‌شده «پروفایل کسب‌وکار» است، نه مالک یا شخص. هر review با وضعیت قبلی، وضعیت جدید، دلیل و زمان در `profile_review_audit` ثبت می‌شود.

## Capability descriptor و انتخاب منبع

`ConnectorRegistry.capabilities()` و `SearchLeadsService.source_capabilities()` یک descriptor پایدار برای هر منبع برمی‌گردانند: نام، پلتفرم، Actor، وضعیت فعال بودن و توضیح. برای انتخاب یک یا چند منبع از `select_sources([...])` استفاده کنید؛ این متد همهٔ نام‌ها را ابتدا اعتبارسنجی می‌کند و تا موفقیت کامل هیچ Connector یا Actorای را فعال نمی‌کند. انتخاب منبع غیرفعال (از جمله social) با `DisabledSourceError` و پیام امن برمی‌گردد. خروجی هر Connector همچنان `SearchResult.source` اختصاصی خود را حفظ می‌کند و نتایج پلتفرم‌ها با هم مخلوط نمی‌شوند.

این API به‌صورت additive اضافه شده و مسیر قدیمی `search(..., source="places")` بدون تغییر کار می‌کند. descriptor فقط metadata محلی است و هیچ تماس پولی با Apify ایجاد نمی‌کند.

### Social Actor contract gates (Phase E)

Official Apify Store references have been recorded for pricing only; they do not authorize execution:

| Platform | Actor | Official page | Published price | Input schema |
|---|---|---|---|---|
| Instagram | `apify~instagram-scraper` | https://apify.com/apify/instagram-scraper | $1.50 / 1,000 results | **Unverified** |
| TikTok | `clockworks~tiktok-scraper` | https://apify.com/clockworks/tiktok-scraper | $1.70 / 1,000 results | **Unverified** |
| LinkedIn Jobs | `dataji~apify-linkdin-jobs` | https://apify.com/dataji/apify-linkdin-jobs | approximately $0.0008 / job result | **Verified for controlled campaign execution** |

`ContractGateReport` requires schema, privacy, and pricing gates to pass. Since the exact input schemas have not been confirmed against the Actor documentation, all three social Actors remain disabled and no paid run is possible. Prices are summaries from the official pages and may change; they are not a budget authorization. Privacy gates exclude person, reviewer, commenter, audience, and viewer data.

### Social Web API (Phase E)

مسیر `POST /api/social-searches` درخواست عمومی اجتماعی را با مدل `SocialSearchRequest` می‌پذیرد: یا `query`/`location` یا `profile_urls` (نه هر دو) و فقط URLهای HTTPS. پیش از هر اجرای احتمالی، نام sourceها از capability registry انتخاب می‌شود. Instagram و TikTok عمداً disabled هستند؛ LinkedIn Jobs از مسیر کمپین قابل انتخاب است و هیچ Actor یا تماس شبکه‌ای ایجاد نمی‌کند. این مسیر فقط برای قرارداد و اعتبارسنجی آماده است و token یا دادهٔ شخصی را نمی‌پذیرد.

## منابع اجتماعی: قرارداد فاز E، اجرا غیرفعال

لایهٔ contract-gated برای Instagram، TikTok و LinkedIn Jobs در `src/connectors/social_profiles.py` آماده است. Instagram و TikTok مدل پروفایل HTTPS دارند؛ LinkedIn Jobs از `LinkedInJobsInput` با `keywords`، `location` و `max_results` استفاده می‌کند. Instagram و TikTok عمداً `enabled=False` هستند؛ LinkedIn Jobs پس از عبور gate از مسیر connector اجرایی کمپین استفاده می‌کند.

Mapping فقط URL عمومی allowlist‌شده، عنوان/handle، bio حرفه‌ای، location، لینک رسمی و metadata محدود پلتفرم (مانند followers/subscribers/videoCount) را نگه می‌دارد. email، owner، reviewer، commenter، comments، audience و viewer data هرگز به خروجی وارد نمی‌شوند. `map_public_profile_safe` به‌جای exception یا دادهٔ خام، کدهای پایدار `malformed_record` و `private_profile` می‌دهد. فعال‌سازی آینده نیازمند تأیید قرارداد Actor، schema/pricing و privacy خواهد بود.

### آداپتورهای منابع اجتماعی و شغلی

برای `apify~instagram-scraper`، `clockworks~tiktok-scraper` و
`dataji~apify-linkdin-jobs` قراردادهای source در
`src/connectors/social_profiles.py` و connector اجرایی LinkedIn Jobs در
`src/connectors/apify_linkedin_jobs.py` وجود دارند. هر آداپتور request preview فیلترشده و allowlist خروجی عمومی دارد؛ LinkedIn Jobs فقط
fields شغلی و شرکتی عمومی (`jobId`، `title`، `companyName`، `location`،
`companyWebsite` و `jobUrl`) را نگه می‌دارد. همهٔ این منابع فعلاً
`enabled=False`، `contract_status=unverified` و
`pricing_status=not_verified` باقی می‌ماند. این وضعیت عمداً بر اساس نبود تأیید
کافی هم‌زمانِ schema عمومی، هزینه و privacy است؛ بنابراین preview قابل اجرا
نیست و هیچ تماس پولی انجام نمی‌شود. وضعیت‌های provider به کدهای پایدار و امن
تبدیل می‌شوند. فیلدهای email، owner، reviewer، commenter/comments، audience و
viewer همیشه خارج از قرارداد خروجی هستند. فعال‌سازی فقط پس از تأیید مستند
schema، قیمت و مجوز privacy مجاز است.

## Instagram business-profile enrichment (offline implementation, disabled by default)

This is a separate confirmed-candidate enrichment operation. Independent Instagram page discovery is now an opt-in source under the profile contract above; the legacy `/api/social-searches` path remains disabled. TikTok is explicitly blocked by user choice; LinkedIn Jobs is unchanged.

The official public [input schema](https://apify.com/apify/instagram-scraper/input-schema) and [Actor documentation](https://apify.com/apify/instagram-scraper.md), checked on 2026-10-11, document discovery with `search` as a comma-separated string (not an array), `searchType: "profile"`, and `searchLimit`; confirmed-candidate profile details use `directUrls`. The adapter sends exactly:

```json
{"resultsType":"details","directUrls":["https://www.instagram.com/example_business/"],"resultsLimit":1,"addParentData":false}
```

The username here is illustrative; no real profile was requested. No search keywords, hashtags, posts/reels URLs, numeric profile IDs, query strings, credentials, ports, or alternate hosts are accepted. A single canonical HTTPS username URL must already belong to a **confirmed** Instagram candidate attached to an existing lead in the selected campaign. Confirmation is checked again before persistence. Returned `private` must be explicitly false, `isBusinessAccount` explicitly true, and username/URL must match the approved profile; otherwise the result is partial with no evidence. No new leads, inferred ownership, contacts or lead-field mutations are produced.

Official details output includes `latestPosts`; the user explicitly relaxed the earlier no-fetch constraint to permit receiving these extras **only for immediate removal**, not persistence/exposure. Ingestion projects scalar, bounded fields `id`, `username`, `url`, `fullName`, `externalUrl` (HTTPS only), `businessCategoryName`, `isBusinessAccount`, `private`, `verified`, then clears the original provider dictionary/page. This excludes biography, posts, captions, comments, follower identities, follower/post/view/engagement metrics, images, nested objects, and all unexpected fields before any raw-record/observation/cache/UI/export handling. The same allowlist is enforced by raw storage. Evidence remains separate from the Lead export contract.

The operation reuses provider attempts, one-shot start, ambiguity→needs_review, persisted-run resume/abort, job fencing/heartbeat, budget reservations and campaign/run/lead/observation lineage. Known runs are resumed instead of restarted; resume uses the existing reservation. Cache holds only persisted references, and enrichment cache **replay is intentionally disabled** so authorization and confirmation cannot be bypassed. Empty, private, non-business or mismatched datasets are partial, not successful. Failed transport/dataset attempts persist safe run failures; raw provider errors and credentials are not recorded.

`GET /api/instagram-enrichment/capability` separately exposes supported/schema-verified/execution-authorized/live-smoke state. Local admission budgets use user-supplied `estimated_cost`, `max_cost`, USD and a reviewed `pricing_version`; these are not a verified live price or a guaranteed provider-side spending cap. Official published pricing may change (the current documentation describes pay-per-event and $2.70/1,000 results on Free); the older Phase E pricing table above is historical, not authorization. Actual costs remain unknown reservations until reconciled. No live smoke/build certification or paid execution has been performed.

## قراردادهای خروجی منبع

هر `SearchResult` علاوه بر Lead مشترک، `projections` تایپ‌شدهٔ منبع را ارائه می‌کند: Google Places برای اطلاعات کسب‌وکار و rating، Google Search برای title/url/snippet، Instagram برای پروفایل عمومی تجاری، و LinkedIn Jobs برای آگهی و اطلاعات حرفه‌ای شرکت. `raw_records` نیز پیش از persistence با allowlist همان منبع فیلتر می‌شوند. دادهٔ reviewer، پست، audience، شخص و استنتاج مالکیت در این قراردادها وجود ندارد. صفحهٔ `/search` این چهار قرارداد را در تب‌های هم‌صفحه نمایش می‌دهد و رفتار مشترک Campaign/Lead/export حفظ شده است.

## خطاهای مهم

- `401/403`: token نامعتبر، revoke شده یا بدون دسترسی؛ token در پیام خطا نمایش داده نمی‌شود
- `404`: Actor ID یا endpoint اشتباه
- `429/5xx/timeout`: خطای موقت؛ client با retry محدود و backoff تلاش می‌کند
- پاسخ ناقص یا بدون run ID: خطای ساختاریافته و بدون دریافت dataset
- dataset خالی: query/location نامناسب یا run ناتمام؛ success جعلی ثبت نمی‌شود

احراز هویت فقط در Header `Authorization` انجام می‌شود و token هرگز در query string، URL یا metadata ذخیره نمی‌شود.

## هزینه و محدودیت

هزینه، سرعت و ظرفیت به تنظیمات Actor، تعداد نتایج و وضعیت حساب Apify بستگی دارد. قبل از اجرای وسیع، با limit کوچک آزمایش کنید. فاز execution اکنون primitive رزرو هزینهٔ اتمیک دارد: مبلغ با Decimal و واحد minor ذخیره می‌شود، currency و pricing version ثبت می‌شوند و هزینهٔ نامعلوم reservation را آزاد نمی‌کند؛ این سقف محلی ضمانت قیمت provider نیست.
