# طراحی MVP رابط کاربری وب

## هدف

افزودن یک پنل وب محلی برای انجام کارهای فعلی پروژه بدون اجرای مداوم CLI. نسخهٔ اول برای یک کاربر روی همان کامپیوتر است و از طریق مرورگر محلی اجرا می‌شود.

## دامنهٔ نسخهٔ اول

- نمایش Dashboard خلاصه: تعداد Campaign، Lead و Runهای اخیر
- ساخت و فهرست Campaign و مشاهدهٔ آمار آن
- فرم اجرای جست‌وجوی `places` با query، location، limit و Campaign
- نمایش نتیجه و وضعیت Run، شامل خطای امن در صورت شکست
- نمایش Leadهای یک Campaign با فیلترهای ساده و pagination محدود
- دانلود JSON و CSV برای Campaign انتخاب‌شده
- حفظ CLI فعلی بدون تغییر رفتاری

خارج از دامنه: احراز هویت، چندکاربره‌بودن، دسترسی اینترنتی، queue توزیع‌شده، منابع اجتماعی و Dashboard تحلیلی پیشرفته.

## معماری

```text
Browser
  -> FastAPI routes
  -> existing SearchLeadsService / LeadStore / repositories
  -> SQLite and Apify Connector
```

رابط وب نباید مستقیماً SQL یا Apify را اجرا کند. Routeها فقط ورودی HTTP را به serviceها بسپارند و برای export از facade فعلی استفاده کنند. منطق مشترک بین CLI و وب در `src/` باقی می‌ماند.

ساختار پیشنهادی:

- `src/web/`: app factory، routeها، schemaهای request/response و template/static adapter
- `templates/`: صفحات HTML
- `tests/test_web_*.py`: تست routeها با dependencyهای mock

FastAPI با templateهای server-rendered و HTML/CSS سبک انتخاب می‌شود تا dependency و پیچیدگی frontend جدا ایجاد نشود.

## جریان جست‌وجو

1. کاربر فرم را ارسال می‌کند.
2. route ورودی را validate می‌کند.
3. `SearchLeadsService.search` موجود اجرا می‌شود.
4. موفقیت یا failure طبق قرارداد فعلی ذخیره می‌شود.
5. route نتیجهٔ قابل‌نمایش و لینک مشاهدهٔ Campaign را برمی‌گرداند.

نسخهٔ اول اجرای جست‌وجو synchronous است؛ تا زمانی که queue لازم نشده، وضعیت در همان request نمایش داده می‌شود. timeout و failure باید پیام امن و status مناسب داشته باشند.

## قراردادهای HTTP اولیه

- `GET /`: dashboard
- `GET /campaigns`: فهرست Campaignها
- `GET /campaigns/new`: فرم ساخت Campaign
- `POST /campaigns`: ساخت Campaign
- `GET /campaigns/{campaign_id}`: آمار و Leadهای Campaign
- `GET /search`: فرم جست‌وجو
- `POST /search`: اجرای Places search
- `GET /campaigns/{campaign_id}/export?format=json|csv`: دانلود خروجی

برای خطاهای validation پاسخ قابل‌فهم HTML نمایش داده شود؛ exception داخلی و token هرگز در UI نمایش داده نشود.

## امنیت و حریم خصوصی

- Bind پیش‌فرض فقط روی `127.0.0.1`.
- token فقط از settings/Environment خوانده شود.
- token، header و traceback در response، template یا log نمایش داده نشوند.
- دادهٔ UI همان دادهٔ عمومی و حرفه‌ای فعلی است؛ اطلاعات خصوصی یا استنتاج مالکیت اضافه نمی‌شود.
- خروجی export از همان مسیر امن فعلی استفاده کند.

## تست و پذیرش

- تست ساخت app و routeهای dashboard، Campaign و export
- تست validation فرم search و campaign
- تست موفقیت search با Connector mock
- تست failure search و عدم نمایش secret
- تست CSV/JSON response و content type
- اجرای کامل `pytest -q`
- اجرای `git diff --check`

## معیار پذیرش

کاربر باید بتواند بدون اجرای commandهای CLI، در مرورگر محلی Campaign بسازد، یک Places search اجرا کند، نتایج را ببیند و JSON/CSV دریافت کند؛ در عین حال CLI قبلی و 79 تست فعلی بدون regression باقی بمانند.
