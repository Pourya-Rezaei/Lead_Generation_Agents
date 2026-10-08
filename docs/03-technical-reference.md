# مرجع فنی

## CLI

```text
leadgen campaign create NAME [--description TEXT] [--id ID] [--db PATH]
leadgen campaign list [--db PATH]
leadgen campaign show CAMPAIGN_ID [--db PATH]
leadgen search QUERY LOCATION [--source places|web] [--limit N] [--campaign ID] [--db PATH]
leadgen export PATH [--format json|csv] [--campaign ID] [--db PATH]
```

Campaignها روی یک دیتابیس مرکزی نگهداری می‌شوند. `create` یک شناسهٔ یکتا می‌سازد یا ID صریح می‌گیرد؛ نام و شناسهٔ تکراری خطا هستند. شناسهٔ Campaign ناشناخته نیز برای search و export رد می‌شود. جست‌وجوی بدون `--campaign` از `general` استفاده می‌کند.

Export بدون `--campaign` رفتار قبلی خود را حفظ می‌کند و همهٔ لیدهای یکتا را می‌دهد. Export با شناسه فقط اعضای همان Campaign را می‌دهد. هر کسب‌وکار یک رکورد اصلی در جدول لیدها دارد و می‌تواند عضو چند Campaign باشد.

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
