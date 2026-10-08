# مدل داده

مدل مرکزی `Lead` نماینده یک کسب‌وکار محلی است.

## فیلدهای اصلی

- `name`: نام کسب‌وکار
- `address`: آدرس قابل نمایش
- `phone`: شماره کاری
- `website`: وب‌سایت
- `category`: عبارت/دسته جست‌وجو
- `rating`: امتیاز منبع
- `reviews`: تعداد reviews
- `source`: منبع رکورد
- `score`: امتیاز کیفیت داخلی

## Campaign و روابط ذخیره‌سازی

- `leads` هر کسب‌وکار را یک‌بار با کلید تطبیق نگه می‌دارد.
- `campaigns` گروه‌های کاری را نگه می‌دارد؛ `general` Campaign پیش‌فرض است.
- `campaign_leads` عضویت چندبه‌چند لید و Campaign را ثبت می‌کند.
- `runs.campaign_id` مشخص می‌کند هر اجرای جست‌وجو متعلق به کدام Campaign است.

یک لید مشترک می‌تواند در چند Campaign دیده شود، بدون اینکه ردیف اصلی آن در `leads` تکثیر شود. عضویت Campaign نخستین و آخرین زمان مشاهده را ثبت می‌کند. خروجی Campaign از آخرین وضعیت Lead می‌آید؛ نسخهٔ تاریخی از فیلدهای Lead در این فاز ساخته نمی‌شود.

## Normalization

نام، فاصله‌ها، URL و مقادیر خالی پیش از ذخیره normalize می‌شوند. رکوردهای یکسان باید با upsert از تکثیر غیرضروری جلوگیری کنند. ماژول `src/quality/normalization.py` کلید canonical را بدون تغییر مقدار نمایشی تولید می‌کند و حروف عربی/فارسی را فقط برای جست‌وجوی هویت همسان می‌سازد.

## Schema version 3: identity و provenance

هر Lead اکنون یک `lead_id` پایدار مستقل از تغییر نام، آدرس یا تلفن دارد. جدول append-only `observations` منبع، source record ID، Run، زمان گردآوری و فیلدهای مشاهده‌شده را نگه می‌دارد و `field_evidence` شواهد هر فیلد را ثبت می‌کند. migration نسخهٔ ۳ برای دیتابیس تازه و legacy idempotent است و در failure rollback می‌شود.

برای سازگاری، `campaign_leads` و export پیش‌فرض فعلاً از کلید legacy استفاده می‌کنند؛ تغییر کامل membership به `lead_id` در migration جداگانه و پس از بررسی دادهٔ واقعی انجام می‌شود. `lead_id` در upsert با source/source_id ثابت می‌ماند، حتی اگر تلفن یا فیلدهای mutable تغییر کند.

## کیفیت و provenance

matching محافظه‌کارانه است: source ID یکسان merge، domain+address یکسان merge، شعبه‌های متفاوت separate و شواهد ضعیف review می‌شوند. نبود evidence به‌معنای false بودن داده نیست و confidence ناشناخته باید ناشناخته بماند. داده‌ای که صرفاً از تشابه نام به دست آمده، مالکیت قطعی محسوب نمی‌شود.

`src/quality/metrics.py` completeness را جدا از score قدیمی محاسبه می‌کند. export CLI فیلترهای اختیاری `--min-completeness`، `--has-phone` و `--has-website` دارد؛ بدون این flags قرارداد JSON/CSV قبلی تغییر نمی‌کند. جدول `lead_merge_audit` دلیل، confidence، زمان و snapshot رکورد ادغام‌شده را نگه می‌دارد تا merge قابل audit و undo باشد.

## حریم خصوصی

تنها داده عمومی و حرفه‌ای کسب‌وکار مجاز است. اطلاعات خصوصی افراد، حدس مالکیت و داده حساس نباید ذخیره یا enrich شود.
