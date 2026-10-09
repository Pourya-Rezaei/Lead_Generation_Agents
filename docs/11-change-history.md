# تاریخچه تغییرات و وضعیت فعلی پروژه

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

## تصمیم‌های باقی‌مانده برای توسعه آینده

- افزودن Connector جدید فقط پس از تعریف source contract، provenance و privacy review.
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
