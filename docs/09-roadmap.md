# نقشه راه

این نقشه راه وضعیت واقعی پروژه را از کارهای انجام‌شده و باقی‌مانده جدا می‌کند.

## تکمیل‌شده: هستهٔ MVP و Campaignها

- اتصال عملیاتی به `compass~crawler-google-places` از طریق Apify
- normalization، scoring و upsert پایهٔ Lead
- migration نسخه‌دار و ذخیره‌سازی SQLite
- ثبت Run، metadata و raw recordهای allowlist شده
- Campaign پیش‌فرض `general`، Campaignهای سفارشی و membership چندبه‌چند Leadها
- export JSON/CSV با فیلتر Campaign
- ثبت Run شکست‌خورده برای خطاهای پیش‌راه‌اندازی و خطاهای Connector
- پیام خطای امن و exit code غیرصفر در CLI
- تست‌های mock شده برای موفقیت، پاسخ malformed، credential، timeout/network، migration و export

## فاز بعدی پیشنهادی: کیفیت داده

این فاز باید قبل از افزودن منابع متعدد انجام شود:

- deduplication صریح و قابل مشاهده بین چند Run و چند منبع
- normalization کامل‌تر تلفن، URL، آدرس و نام کسب‌وکار
- provenance و evidence برای هر فیلد مهم
- تفکیک completeness، confidence و lead score
- فیلتر export بر اساس score، وجود وب‌سایت و کیفیت داده
- تست regression برای رکوردهای تکراری و داده‌های ناقص

## فاز پس از کیفیت داده: منابع تکمیلی

- افزودن `apify/google-search-scraper` برای اطلاعات عمومی تکمیلی و وب‌سایت رسمی
- افزودن تدریجی:
  - `apify/instagram-scraper`
  - `clockworks/tiktok-scraper`
  - `streamers/youtube-scraper`
- اتصال هر profile فقط با evidence و سطح اطمینان به کسب‌وکار؛ match ضعیف باید `probable` بماند.

## فاز پلتفرم اجرا

- queue و اجرای async
- cache و idempotency
- داشبورد وب محلی
- history و مقایسهٔ Runها
- export به CRM
- budget guard و rate-limit policy

## خارج از محدوده فعلی

- Google Maps API رسمی
- جمع‌آوری داده خصوصی یا reviewer/person data
- استنتاج مالکیت افراد از قرائن
- اجرای خودکار حجم بالا بدون کنترل هزینه
