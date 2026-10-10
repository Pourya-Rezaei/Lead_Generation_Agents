# مستندات Local Lead Generation Agents

این پوشه مرجع اصلی شناخت، اجرا، توسعه و نگهداری پروژه است. این پروژه یک CLI پایتونی برای پیدا کردن لیدهای کسب‌وکار محلی بر اساس **شهر** و **شغل/عبارت جست‌وجو** است.

## وضعیت فعلی

نسخهٔ فعلی یک MVP عملیاتی برای منبع Google Places است:

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
- تست‌های unit و integration کاملاً mock شده؛ ماتریس محلی Python 3.10 تا 3.14 با ۱۹۷ تست موفق در هر نسخه
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
- تست کامل محلی: `197 passed` روی هرکدام از Python 3.10، 3.11، 3.12، 3.13 و 3.14؛ اجرای remote در GitHub Actions هنوز انجام نشده است

منبع `web` و Connectorهای Instagram و TikTok فعال نیستند. LinkedIn Jobs برای اجرای کنترل‌شده در کمپین‌ها فعال شده و در رابط وب قابل انتخاب است.
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
