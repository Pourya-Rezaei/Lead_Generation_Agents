# معماری

## جریان داده

```text
CLI -> Settings -> Connector -> Apify Actor -> Dataset
    -> Lead mapping -> normalize -> score -> SQLite -> JSON/CSV
```

## اجزا

- CLI: اعتبارسنجی ورودی و نمایش نتیجه؛ بدون orchestration یا scraping logic.
- `SearchLeadsService`: اجرای use case، lifecycle اجرا، ذخیره لید و metadata.
- `ConnectorRegistry`: انتخاب منبع؛ در MVP فقط `places` فعال است و `web` غیرفعال است.
- Connector: اجرای منبع و برگرداندن `SearchResult` شامل leads، status، provenance و raw records محدود.
- Domain: مدل `Lead`، نرمال‌سازی، validation، امتیازدهی و تطبیق هویت.
- Storage: migration نسخه‌دار SQLite، repositoryها، upsert و export.
- Apify client: authentication امن، timeout، retry محدود و دریافت Actor/dataset.

## تصمیم‌های طراحی

- Apify پشت Connector پنهان است.
- token فقط از Environment خوانده می‌شود.
- Actor ID در URL API با `~` نوشته می‌شود.
- اجرای Places با `waitForFinish=60` انجام می‌شود.
- منبع هر رکورد با `source` مشخص می‌شود.

## توسعه آینده

Connectorهای Instagram، TikTok و YouTube باید همین قرارداد را پیاده کنند. تطبیق social profile باید امتیاز و evidence داشته باشد و صرفاً بر اساس نام ادغام نشود.
