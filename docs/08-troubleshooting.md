# عیب‌یابی

## Current release boundary (2026-10-11)

Only Google Places and independent Instagram Search are executable. Instagram is standard-only (`liveSearch=false`, enhancement=false), one comma-free phrase, default 10 and limit 1..250. Requests, profiles, reload and exports are source-specific; no contact extraction or geographic guarantee. Existing SQLite/history are preserved. Any references below to Google Search, LinkedIn, YouTube, TikTok or Instagram enrichment are **historical**, not active product capabilities. See [the current integration contract](06-apify-integration.md) and [operations](02-operations-guide.md). No paid smoke or live-mode certification was performed.


## `APIFY_API_TOKEN is required`

فایل `.env` در پوشه اجرای command وجود ندارد، token خالی است یا settings آن را بارگذاری نمی‌کند. مقدار token را بررسی و shell را دوباره فعال کنید.

## خطای `404 Not Found` در Actor

شناسه API باید این باشد:

```text
compass~crawler-google-places
```

نه مسیر دارای slash یعنی `compass/crawler-google-places`.

## `Saved 0 leads`

Actor ممکن است هنوز تمام نشده باشد، query/location نتیجه نداشته باشد یا dataset اشتباه خوانده شود. اجرای جدید با `--limit 5` و عبارت ساده انگلیسی را برای تشخیص امتحان کنید و run/dataset را در Apify Console ببینید.

## token افشا شده

فوراً token را revoke کنید، token جدید بسازید و `.env` را اصلاح کنید. token قدیمی را در history یا log بازنشر نکنید.

## بررسی metadata و raw data

اطلاعات run و raw recordها داخل همان SQLite database ذخیره می‌شوند:

```bash
sqlite3 leads.db 'SELECT payload FROM runs ORDER BY rowid DESC LIMIT 5;'
sqlite3 leads.db 'SELECT run_id, COUNT(*) FROM raw_records GROUP BY run_id;'
```

## خروجی در ریشه پروژه

اگر فقط نام فایل بدهید، مثلاً `dentists.json`، خروجی در پوشه فعلی می‌رود. برای پوشه مشخص:

```bash
mkdir -p exports
leadgen export exports/dentists.json --format json
```

## تست شکست خورد

محیط مجازی و نصب editable را بررسی کنید:

```bash
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
```
