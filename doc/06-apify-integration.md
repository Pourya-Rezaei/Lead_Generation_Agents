# یکپارچه‌سازی Apify

## Actor فعلی

```text
compass~crawler-google-places
```

این Actor از طریق API آپیفای اجرا می‌شود و به Google Maps API key نیاز ندارد. کلید موردنیاز فقط `APIFY_API_TOKEN` است.

## ورودی

نمونه مفهومی:

```json
{
  "searchStringsArray": ["دندانپزشکی"],
  "locationQuery": "تهران",
  "maxCrawledPlacesPerSearch": 20
}
```

## API flow

1. `POST /v2/acts/compass~crawler-google-places/runs`
2. ارسال Bearer token در Header
3. انتظار برای پایان run با `waitForFinish=60`
4. خواندن `defaultDatasetId`
5. `GET /v2/datasets/{datasetId}/items`
6. mapping رکوردها به `Lead`
7. ثبت metadata اجرا و رکوردهای خام در SQLite

توکن نباید در query string قرار گیرد؛ این کار مانع نمایش آن در URL و traceback می‌شود. اجرای موفق، شناسه run، dataset و تعداد رکوردها را در جدول‌های `runs` و `raw_records` ثبت می‌کند.

## وضعیت پیاده‌سازی فاز ۲

اجرای واقعی با query `دندانپزشکی`، location `تهران` و limit برابر ۵ با موفقیت انجام شد. پنج لید در SQLite ذخیره شد و exportهای JSON و CSV در `exports/phase2/` ساخته شدند. تست‌های خودکار نیز با نتیجه `4 passed` موفق هستند.

## خطاهای مهم

- `401/403`: token نامعتبر، revoke شده یا بدون دسترسی؛ token در پیام خطا نمایش داده نمی‌شود
- `404`: Actor ID یا endpoint اشتباه
- `429/5xx/timeout`: خطای موقت؛ client با retry محدود و backoff تلاش می‌کند
- پاسخ ناقص یا بدون run ID: خطای ساختاریافته و بدون دریافت dataset
- dataset خالی: query/location نامناسب یا run ناتمام؛ success جعلی ثبت نمی‌شود

احراز هویت فقط در Header `Authorization` انجام می‌شود و token هرگز در query string، URL یا metadata ذخیره نمی‌شود.

## هزینه و محدودیت

هزینه، سرعت و ظرفیت به تنظیمات Actor، تعداد نتایج و وضعیت حساب Apify بستگی دارد. قبل از اجرای وسیع، با limit کوچک آزمایش کنید.
