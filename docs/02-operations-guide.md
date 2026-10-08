# راهنمای عملیات

## اجرای معمول

1. محیط مجازی را فعال کنید.
2. وجود `APIFY_API_TOKEN` را بررسی کنید.
3. جست‌وجو را با `--limit` کنترل‌شده اجرا کنید.
4. خروجی را در `exports/` ذخیره کنید.
5. SQLite و خروجی‌ها را backup کنید.

## اجرای پنل وب محلی

```bash
uvicorn src.web.app:app --host 127.0.0.1 --port 8000
```

پنل در <http://127.0.0.1:8000> باز می‌شود. برای توقف سرور `Ctrl+C` بزنید. bind پیش‌فرض فقط localhost است؛ برای دسترسی شبکه‌ای یا اینترنتی این نسخه را تغییر ندهید.

## اجرای جداگانه

```bash
leadgen search "رستوران" "شیراز" --source places --db data/shiraz.db
leadgen export data/shiraz.json --format json --db data/shiraz.db
```

## مدیریت هزینه

- با limit کوچک شروع کنید.
- query دقیق بنویسید.
- شهرهای بزرگ را به منطقه تقسیم کنید.
- Actorهای شبکه‌های اجتماعی را در MVP فعال نکنید.
- runها را در Apify Console بررسی کنید.

## گزارش تست فاز ۲

در تاریخ ۲۰۲۶-۱۰-۰۷، فاز دوم با موفقیت اعتبارسنجی شد:

```text
pytest -q                 -> 4 passed
Places search limit=5    -> Saved 5 leads
JSON export              -> successful
CSV export               -> successful
SQLite database          -> test-phase2.db (48K)
```

فایل‌های آزمون در مسیر `exports/phase2/` تولید شدند. برای تست‌های بعدی از database جداگانه استفاده کنید تا `leads.db` اصلی تغییر نکند.

## مدیریت secret

در صورت افشای token، فوراً آن را در Apify revoke و token جدید ایجاد کنید. `.env` نباید commit شود.
