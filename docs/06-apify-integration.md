# یکپارچه‌سازی Apify

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

Client اکنون lifecycle را به عملیات مستقل تقسیم می‌کند: `start_actor`، `get_run`، `dataset_items` و `abort_run`. wrapper قدیمی `run_actor` برای سازگاری باقی مانده و از همان مسیر start استفاده می‌کند.

1. `POST /v2/acts/compass~crawler-google-places/runs`
2. ارسال Bearer token در Header
3. انتظار برای پایان run با `waitForFinish=60`
4. خواندن `defaultDatasetId`
5. `GET /v2/datasets/{datasetId}/items`
6. mapping رکوردها به `Lead`
7. ثبت metadata اجرا و رکوردهای خام در SQLite
8. در صورت شکست اجرای جست‌وجو، ثبت Run ناموفق در Campaign

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

## منابع اجتماعی: قرارداد آماده، اجرا غیرفعال

قرارداد mapping مشترک برای Instagram، TikTok و YouTube در `src/connectors/social_profiles.py` آماده است. فقط URL عمومی HTTPS، عنوان/handle، bio حرفه‌ای و لینک رسمی احتمالی نگه داشته می‌شوند؛ email، comment، reviewer، audience و دادهٔ شخصی حذف می‌شوند. هر سه connector تا contract gate رسمی Actor، بررسی schema/pricing و تأیید privacy، `disabled` باقی می‌مانند.

## خطاهای مهم

- `401/403`: token نامعتبر، revoke شده یا بدون دسترسی؛ token در پیام خطا نمایش داده نمی‌شود
- `404`: Actor ID یا endpoint اشتباه
- `429/5xx/timeout`: خطای موقت؛ client با retry محدود و backoff تلاش می‌کند
- پاسخ ناقص یا بدون run ID: خطای ساختاریافته و بدون دریافت dataset
- dataset خالی: query/location نامناسب یا run ناتمام؛ success جعلی ثبت نمی‌شود

احراز هویت فقط در Header `Authorization` انجام می‌شود و token هرگز در query string، URL یا metadata ذخیره نمی‌شود.

## هزینه و محدودیت

هزینه، سرعت و ظرفیت به تنظیمات Actor، تعداد نتایج و وضعیت حساب Apify بستگی دارد. قبل از اجرای وسیع، با limit کوچک آزمایش کنید. فاز execution اکنون primitive رزرو هزینهٔ اتمیک دارد: مبلغ با Decimal و واحد minor ذخیره می‌شود، currency و pricing version ثبت می‌شوند و هزینهٔ نامعلوم reservation را آزاد نمی‌کند؛ این سقف محلی ضمانت قیمت provider نیست.
