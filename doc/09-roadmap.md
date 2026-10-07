# نقشه راه

## فاز ۱: تثبیت MVP

- ثبت raw response و source URL
- run summary و وضعیت `partial`
- retry/backoff و خطای ساختاریافته
- deduplication چندمنبعی
- completeness/confidence دقیق‌تر

## فاز ۲: منابع اجتماعی

Actorهای پیشنهادی:

- `apify/instagram-scraper`
- `clockworks/tiktok-scraper`
- `streamers/youtube-scraper`

هر profile باید با نام، شهر، وب‌سایت و evidence به کسب‌وکار متصل شود؛ match ضعیف باید `probable` بماند نه قطعی.

## فاز ۳: پلتفرم اجرا

- queue و اجرای async
- cache و idempotency
- داشبورد وب محلی
- history و مقایسه runها
- export به CRM
- budget guard و rate-limit policy

## خارج از محدوده فعلی

- Google Maps API رسمی
- جمع‌آوری داده خصوصی
- استنتاج مالکیت افراد
- اجرای خودکار حجم بالا بدون کنترل هزینه
