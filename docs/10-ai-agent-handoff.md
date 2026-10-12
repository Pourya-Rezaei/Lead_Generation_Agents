# راهنمای تحویل به ایجنت هوش مصنوعی

## Current release boundary (2026-10-11)

Only Google Places and independent Instagram Search are executable. Instagram is standard-only (`liveSearch=false`, enhancement=false), one comma-free phrase, default 10 and limit 1..250. Requests, profiles, reload and exports are source-specific; no contact extraction or geographic guarantee. Existing SQLite/history are preserved. Any references below to Google Search, LinkedIn, YouTube, TikTok or Instagram enrichment are **historical**, not active product capabilities. See [the current integration contract](06-apify-integration.md) and [operations](02-operations-guide.md). No paid smoke or live-mode certification was performed.


## قبل از تغییر

1. `docs/README.md` و `README.md` را بخوان.
2. وضعیت Git و فایل‌های تغییرکرده را بررسی کن.
3. `.env` و tokenها را هرگز نمایش نده.
4. قرارداد `Lead` و Connector را بشناس.
5. تست‌های فعلی را اجرا کن.

## نقاط ورود

- CLI: `src/cli.py`
- تنظیمات: `src/config.py`
- domain: `src/domain.py`
- storage: `src/storage.py`
- Apify Places: `src/connectors/apify_places.py`
- tests: `tests/`

## قواعد توسعه

- Connector جدید را از CLI جدا نگه دار.
- token را فقط از Environment بخوان.
- از Google API key استفاده نکن مگر تصمیم معماری جدید و مستند وجود داشته باشد.
- برای هر تغییر تست اضافه یا اصلاح کن.
- داده عمومی حرفه‌ای را نگه دار و داده خصوصی را جمع نکن.
- تغییرات غیرمرتبط انجام نده.
- خروجی و schema فعلی را بدون migration نشکن.

## چک‌لیست پایان کار

```bash
pytest -q
grep -RInE 'APIFY_API_TOKEN|GOOGLE_API_KEY' --exclude-dir=.venv --exclude-dir=.git .
```

در گزارش نهایی این موارد را بنویس: فایل‌های تغییرکرده، رفتار جدید، تست اجراشده، محدودیت‌های باقی‌مانده و migration موردنیاز.

## وضعیت فعلی پروژه

- منبع رسمی فعال فعلی فقط `places` و Actor مربوط به `compass~crawler-google-places` است.
- Apify Places در اجرای واقعی با limit پایین تست شده است؛ تست‌های پروژه به‌صورت mock و بدون token واقعی اجرا می‌شوند.
- آخرین اعتبارسنجی کامل در branch فاز A: `93 passed` با `pytest -q`؛ baseline main قبل از فاز A برابر 89 بود.
- Campaign پیش‌فرض `general` است و جست‌وجو می‌تواند با `--campaign ID` به Campaign مشخص متصل شود.
- `campaign create/list/show` و export محدودشده با `--campaign` فعال هستند.
- خطاهای credential، timeout/network، پاسخ malformed و failure result به‌صورت Run ناموفق ثبت می‌شوند؛ Lead و raw برای failure ذخیره نمی‌شوند.
- خروجی export با syntax فعلی به شکل `export PATH --format csv|json [--campaign ID] [--db PATH]` است؛ گزینهٔ `--output` وجود ندارد.
- `web` و Connectorهای Instagram، TikTok و YouTube هنوز فعال نیستند.
- پنل وب محلی MVP با FastAPI/Jinja فعال است؛ راه‌اندازی آن با `uvicorn src.web.app:app --host 127.0.0.1 --port 8000` انجام می‌شود و فقط Places، Campaign، مشاهده Lead و export را پوشش می‌دهد.
- برای اجرای روزمره از ریشهٔ checkout اصلی استفاده شود؛ worktree جداگانه‌ای برای این پروژه لازم نیست.

## وضعیت Campaignها

- Campaign پیش‌فرض `general` هنگام initialize دیتابیس ساخته می‌شود.
- Run هر جست‌وجو به Campaign وصل است؛ `--campaign ID` یک Campaign مشخص می‌کند.
- `campaign create/list/show` مدیریت Campaignها را فراهم می‌کند.
- یک Lead می‌تواند عضو چند Campaign باشد؛ جدول اصلی `leads` رکورد یکتا را نگه می‌دارد.
- ذخیرهٔ نتیجهٔ جست‌وجو (Run، Leadها، عضویت‌ها و raw recordهای مجاز) در یک تراکنش انجام می‌شود.
- export سراسری همچنان پیش‌فرض است؛ `--campaign ID` خروجی را به همان Campaign محدود می‌کند.
- برای کارهای روزمره از همان دیتابیس مرکزی استفاده کنید. `--db PATH` فقط وقتی به مسیر دیگری نیاز دارید صریحاً انتخاب شود.

نمونهٔ commandها و رفتار فیلتر در `docs/01-getting-started.md` و `docs/03-technical-reference.md` آمده است.

## فرض‌های فعلی

- اجرای CLI از ریشه پروژه انجام می‌شود.
- SQLite محلی و تک‌کاربره است.
- Places تنها منبع رسمی فعال MVP است.
- Actorهای اجتماعی هنوز فعال نیستند.
