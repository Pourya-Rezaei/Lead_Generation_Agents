# راهنمای تحویل به ایجنت هوش مصنوعی

## قبل از تغییر

1. `docs/README.md` و `README.md` را بخوان.
2. وضعیت Git و فایل‌های تغییرکرده را بررسی کن.
3. `.env` و tokenها را هرگز نمایش نده.
4. قرارداد `Lead` و Connector را بشناس.
5. تست‌های فعلی را اجرا کن.

## نقاط ورود

- CLI: `leadgen/cli.py`
- تنظیمات: `leadgen/config.py`
- domain: `leadgen/domain.py`
- storage: `leadgen/storage.py`
- Apify Places: `leadgen/connectors/apify_places.py`
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

## وضعیت فعلی پس از فاز ۲

- Apify Places در اجرای واقعی با limit=5 تست شده است.
- تست خودکار فعلی: `4 passed`.
- metadata run و raw records در SQLite ثبت می‌شوند.
- export تو در تو با ساخت خودکار پوشه کار می‌کند.
- برای آزمایش واقعی از `test-phase2.db` استفاده شده و نباید با `leads.db` اصلی اشتباه شود.

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
