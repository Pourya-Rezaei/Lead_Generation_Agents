# تست و کیفیت

## اجرای تست

```bash
source .venv/bin/activate
pytest -q
```

## انواع تست فعلی

- Connector با HTTP mock شده
- mapping و normalization
- scoring
- SQLite round-trip
- export JSON/CSV

## قانون تست تغییرات

هر تغییر در schema، connector یا storage باید حداقل یک تست regression داشته باشد. تست‌ها نباید token واقعی یا شبکه واقعی مصرف کنند.

## نتیجه آخرین اعتبارسنجی

```text
pytest -q                              4 passed
leadgen search ... --limit 5           Saved 5 leads
leadgen export ...json                 successful
leadgen export ...csv                  successful
```

برای جلوگیری از تغییر دیتابیس اصلی، اجرای واقعی با `test-phase2.db` انجام شد. خروجی‌ها در `exports/phase2/` ذخیره شدند.

## کنترل دستی MVP

بعد از یک run واقعی بررسی کنید:

- تعداد نتایج با limit سازگار است.
- نام و آدرس خالی نیستند.
- source برابر منبع صحیح است.
- فایل JSON معتبر است.
- CSV با Excel/CRM باز می‌شود.
