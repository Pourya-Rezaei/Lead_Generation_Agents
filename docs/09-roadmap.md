# نقشه راه

## وضعیت اجرایی فعلی (2026-10-10)

- SQLite schema: نسخهٔ 17.
- آخرین اجرای کامل پس از اصلاحات: 214 تست موفق روی Python 3.14 و یک هشدار deprecation از Starlette/httpx. ماتریس کامل قبلی روی Python 3.10 تا 3.14، پیش از این اصلاحات، در هر نسخه 197 تست موفق داشت؛ اجرای remote GitHub Actions هنوز تأیید نشده است.
- منبع‌های فعال: Google Places و Google Search؛ LinkedIn Jobs برای اجرای کنترل‌شده فعال است. Instagram و TikTok در registry غیرفعال‌اند، `web` غیرفعال است و YouTube connector فعال ندارد.
- اجرای ناهمگام Job، worker، lease/fencing، heartbeat، بودجه، cache replay و lineage، maintenance و retention، backup/restore و readiness پیاده‌سازی شده‌اند.
- Provider lifecycle از attempt پایدار و resume استفاده می‌کند. شروع Actor نباید پس از نتیجهٔ مبهم کورکورانه retry شود؛ موارد مبهم به `needs_review` می‌روند. لغو Job تلاش می‌کند run شناخته‌شده را abort کند و حالت شروع هم‌زمان پس از دریافت run ID دوباره بررسی می‌شود.
- رابط وب فارسی/RTL و CLI برای مدیریت Campaign، جست‌وجو، Job، منابع و export موجودند. Web UI همچنان local-only و بدون احراز هویت است؛ آن را روی شبکهٔ عمومی bind نکنید.
- همهٔ تست‌های Apify باید با mock اجرا شوند؛ اجرای زندهٔ Actor پولی بخشی از suite نیست. CI چندنسخه‌ای پیکربندی شده، اما GitHub Actions remote تا زمان اتصال repository و اجرای workflow تأیید نشده است.
- دادهٔ خام Places allowlist می‌شود؛ شمارش aggregate `reviewsCount` می‌تواند نگه‌داری شود، اما متن/مشخصات reviewer در محدودهٔ جمع‌آوری نیست.

این سند، قابلیت‌های فعلی را از تصمیم‌های آینده جدا می‌کند؛ موارد تاریخی یا کامل‌شده نباید به‌عنوان کار باقی‌مانده تعبیر شوند.

## تکمیل‌شده

### داده و Campaignها

- جست‌وجوی Places و Google Search با Apify و مدل استاندارد Lead
- normalization، scoring، provenance، evidence، confidence و deduplication
- Campaign پیش‌فرض `general`، membership چندبه‌چند، export JSON/CSV و ثبت Runهای ناموفق
- schema migration نسخه‌دار، کلید اصلی `(campaign_id, lead_id)` و cache replay با lineage لید/observation/raw record

### اجرا و عملیات

- queue و worker چندفرایندی، atomic claim، fencing، heartbeat و بازیابی پس از crash
- lifecycle پایدار Provider، resume، cancellation و مسیر دستی `needs_review`
- budget reservation، idempotency، تاریخچهٔ اجرا و readiness بر پایهٔ schema/heartbeat
- backup/restore و maintenance/retention با حفاظت از lineage
- import بدون side effect برای اپلیکیشن و اجرای محلی Uvicorn
- CI matrix پیکربندی‌شده برای Python 3.10–3.14؛ اجرای remote همچنان نیازمند دسترسی GitHub است

### رابط‌ها

- پنل محلی FastAPI/Jinja با پشتیبانی فارسی و RTL، Campaignها، جست‌وجو، Jobها، منابع، بازبینی پروفایل و export
- CLI برای جست‌وجو، Campaign و export

## کارهای آینده و تصمیم‌های باز

- اجرای و تأیید GitHub Actions روی repository remote؛ نتیجهٔ محلی جایگزین اجرای remote نیست.
- smoke زندهٔ Apify فقط با تأیید جداگانه، token مجاز، limit پایین و بودجهٔ کنترل‌شده؛ اجرای Actor پولی خودکار یا بخشی از تست‌ها نیست.
- بازبینی دستی Jobهای `needs_review`؛ retry فقط پس از تأیید نبودن run سمت Provider.
- احراز هویت و چندکاربره‌بودن، پیش از هرگونه دسترسی شبکه‌ای به پنل.
- توسعهٔ CRM export یا scheduling فقط پس از تعیین نیاز و قراردادهای عملیاتی.
- فعال‌سازی Instagram، TikTok یا YouTube منوط به تأیید schema، هزینه، حریم خصوصی و contract gate است؛ استخراج reviewer/person data خارج از محدوده است.

## خارج از محدوده

- Google Maps API رسمی
- جمع‌آوری دادهٔ خصوصی یا اطلاعات reviewer/person
- استنتاج مالکیت اشخاص از قرائن ضعیف
- اجرای خودکار حجم بالا بدون کنترل هزینه و بازبینی انسانی
