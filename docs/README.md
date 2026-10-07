# مستندات Local Lead Generation Agents

این پوشه مرجع اصلی شناخت، اجرا، توسعه و نگهداری پروژه است. این پروژه یک CLI پایتونی برای پیدا کردن لیدهای کسب‌وکار محلی بر اساس **شهر** و **شغل/عبارت جست‌وجو** است.

## وضعیت فعلی

MVP فعلی:

- ورودی CLI برای query، location، source و limit
- اجرای Actor `compass~crawler-google-places` از طریق Apify
- دریافت dataset و تبدیل آن به مدل استاندارد لید
- ذخیره در SQLite
- نرمال‌سازی، امتیازدهی و upsert
- خروجی JSON و CSV
- منبع `web` برای جست‌وجوی سبک HTTP
- تست‌های unit و integration mock شده
- ثبت metadata اجرای Apify در جدول `runs`
- ذخیره رکوردهای خام dataset در جدول `raw_records`
- ساخت خودکار پوشه مقصد هنگام export
- تست end-to-end موفق با ۵ لید واقعی و خروجی JSON/CSV

Google Maps API رسمی در پروژه استفاده نمی‌شود؛ فقط `APIFY_API_TOKEN` لازم است.

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

## ساختار کد

- `leadgen/cli.py`: دستورات CLI
- `leadgen/config.py`: تنظیمات Environment
- `leadgen/domain.py`: مدل لید، normalization و scoring
- `leadgen/storage.py`: SQLite و export
- `leadgen/connectors/`: اتصال به منابع داده
- `tests/`: تست‌های پروژه
- `.env`: تنظیمات محلی و secretها؛ هرگز commit نشود

## اصل مهم حریم خصوصی

فقط داده‌های عمومی و حرفه‌ای مرتبط با کسب‌وکار جمع‌آوری شود. سیستم نباید مالکیت شخصی را از روی قرائن حدس بزند یا داده خصوصی جمع کند.
