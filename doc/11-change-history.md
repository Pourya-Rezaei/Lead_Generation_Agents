# تاریخچه تغییرات و وضعیت فعلی پروژه

این سند خلاصه‌ای از کارهای انجام‌شده در مرحله تثبیت پروژه را ثبت می‌کند تا تصمیم‌های فنی، تغییرات معماری و معیارهای اعتبارسنجی برای ایجنت یا توسعه‌دهنده بعدی قابل پیگیری باشد.

## دامنه کار انجام‌شده

- ممیزی کامل ساختار، کد، تست‌ها، مستندات، امنیت، حریم خصوصی و کارایی.
- طراحی برنامه اصلاح مرحله‌ای به‌جای بازنویسی کامل.
- افزودن Git و ایجاد branch اصلی `main`.
- ایجاد اولین commit پروژه با پیام `chore: initialize project version control`.
- اجرای تست‌های آفلاین و بدون درخواست واقعی به Apify.

## تغییرات معماری

### Apify

- ایجاد Client واحد در `leadgen/apify.py`.
- ارسال credential فقط با Header احراز هویت؛ token در URL یا پیام خطا قرار نمی‌گیرد.
- طبقه‌بندی خطاهای credential، endpoint، timeout، خطاهای موقت و پاسخ malformed.
- retry محدود و قابل‌تزریق با backoff.

### قرارداد Connector

- ایجاد `RunStatus` و `SearchResult` در `leadgen/results.py`.
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

- migration نسخه‌دار، idempotent و transaction-based در `leadgen/migrations.py`.
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
pytest -q          -> 44 passed
pip check          -> No broken requirements found
Pylance diagnostics -> no errors
CLI --help         -> successful
```

هیچ اجرای زنده‌ای علیه Apify در این مرحله انجام نشد.

## تصمیم‌های باقی‌مانده برای توسعه آینده

- افزودن Connector جدید فقط پس از تعریف source contract، provenance و privacy review.
- طراحی queue یا اجرای async فقط بعد از اثبات نیاز عملیاتی.
- افزودن CI پس از اتصال repository به remote.
- تعیین سیاست retention مطابق نیاز واقعی کسب‌وکار و قوانین محل اجرا.
- ایجاد migration جدید به‌صورت ترتیبی و بدون شکستن JSON/CSV پیش‌فرض.

## وضعیت Git

- branch اصلی: `main`
- commit اولیه: `88ee07b9b52babb69025d41ae39fa29a8a7a3386`
- فایل‌های حساس در commit اولیه وارد نشده‌اند.
