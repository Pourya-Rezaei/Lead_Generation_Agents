# مرجع فنی

## CLI

```text
leadgen search QUERY LOCATION [--source places|web] [--limit N] [--db PATH]
leadgen export PATH [--format json|csv] [--db PATH]
```

`places` به Apify token نیاز دارد؛ منبع `web` در وضعیت فعلی feature-disabled است و درخواست HTTP ارسال نمی‌کند.

## Environment

| متغیر | الزامی | پیش‌فرض | توضیح |
|---|---:|---|---|
| `APIFY_API_TOKEN` | برای Places | ندارد | token احراز هویت Apify |
| `DATABASE_PATH` | خیر | `leads.db` | SQLite database |
| `HTTP_TIMEOUT` | خیر | تنظیم پروژه | timeout درخواست |

`GOOGLE_API_KEY` و Google Maps API در این پروژه استفاده نمی‌شوند.

## قرارداد Connector

Connector متد `search(query, location, limit)` دارد و `list[Lead]` برمی‌گرداند. mapping response باید از domain و CLI جدا بماند.

## خروجی

JSON برای مصرف ماشینی و CSV برای Excel/CRM است. هر رکورد باید source و امتیازهای کیفیت را حفظ کند.
