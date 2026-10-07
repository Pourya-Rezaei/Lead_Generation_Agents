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

## جست‌وجوی Places

```bash
leadgen search "دندانپزشکی" "تهران" --source places --limit 20
```

Actor `compass~crawler-google-places` اجرا و dataset آن در `leads.db` ذخیره می‌شود.

## خروجی

```bash
mkdir -p exports
leadgen export exports/dentists-tehran.json --format json
leadgen export exports/dentists-tehran.csv --format csv
```

مسیر نسبی نسبت به پوشه اجرای command است.

## تست

```bash
pytest -q
```
