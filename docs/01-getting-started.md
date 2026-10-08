# شروع سریع

## پیش‌نیازها

- Python 3.11 یا جدیدتر
- حساب Apify و API token
- دسترسی شبکه به `api.apify.com`

## نصب

```bash
cd /home/pouria/Projects/Personal/Local_Lead_Generation_Agents
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
cp .env.example .env
```

## تنظیم محیط

```env
APIFY_API_TOKEN=YOUR_NEW_APIFY_TOKEN
DATABASE_PATH=leads.db
HTTP_TIMEOUT=60
```

توکن را در command، log، Git یا مستندات عمومی قرار ندهید.

## ساخت Campaign و جست‌وجو

Campaign کمک می‌کند جست‌وجوها و لیدهای مرتبط را زیر یک شناسه نگه دارید:

```bash
leadgen campaign create "دندان‌پزشکی تجریش" --id tajrish-dental
leadgen search "دندانپزشکی" "تجریش تهران" --source places --limit 20 --campaign tajrish-dental
leadgen campaign list
leadgen campaign show tajrish-dental
```

Actor `compass~crawler-google-places` اجرا و dataset آن در دیتابیس مرکزی ذخیره می‌شود. اگر `--campaign` را حذف کنید، جست‌وجو به Campaign پیش‌فرض `general` («جست‌وجوهای عمومی») وصل می‌شود. برای همهٔ فرمان‌ها همان دیتابیس را انتخاب کنید؛ `--db PATH` مسیر دیتابیس را صریح می‌کند.

## اجرای Job از CLI

برای ارسال یک جست‌وجوی صف‌شده، کلید idempotency را صریح تعیین کنید:

```bash
leadgen jobs submit دندانپزشکی تهران --idempotency-key search-001
leadgen jobs status JOB_ID
leadgen jobs cancel JOB_ID
```

این دستورات Job را ثبت و کنترل می‌کنند؛ برای اجرای آن‌ها هنوز باید worker جداگانه اجرا شود.

## پنل وب محلی

برای استفاده بدون اجرای مداوم CLI، از ریشهٔ پروژه اجرا کنید:

```bash
uvicorn src.web.app:app --host 127.0.0.1 --port 8000
```

سپس در مرورگر به <http://127.0.0.1:8000> بروید. پنل نسخهٔ اول ساخت Campaign، اجرای جست‌وجوی Places، مشاهدهٔ لیدهای Campaign و دانلود JSON/CSV را پشتیبانی می‌کند. این نسخه فقط روی همان کامپیوتر قابل دسترسی است.

## خروجی

```bash
mkdir -p exports
leadgen export exports/tajrish-dental.json --format json --campaign tajrish-dental
leadgen export exports/all-leads.csv --format csv
```

بدون `--campaign` همهٔ لیدهای یکتای دیتابیس صادر می‌شوند؛ با آن فقط اعضای همان Campaign. مسیر نسبی خروجی نسبت به پوشهٔ اجرای command است. دیتابیس خالی یا آزمایشی جداگانه را می‌توانید با `--db data/test.db` انتخاب کنید.

## تست

```bash
pytest -q
```
