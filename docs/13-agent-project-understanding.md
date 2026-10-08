# راهنمای درک پروژه برای Agent

این سند مشخص می‌کند Agent جدید چگونه باید پروژه را بفهمد، بدون اینکه از ابتدا مستقیماً وارد خواندن همه فایل‌های کد شود.

هدف این workflow این است که Agent ابتدا **مستندات، حافظه معماری و graph پروژه** را بخواند، سپس فقط source code مرتبط با سؤال یا تغییر را بررسی کند.

## اصل اصلی

Agent نباید با بازکردن تصادفی فایل‌های `src/` شروع کند.

ترتیب صحیح:

```text
قواعد Agent
  → نمای کلی مستندات
  → handoff و تاریخچه تصمیم‌ها
  → وضعیت CBM
  → معماری و graph
  → تعیین محدوده مرتبط
  → خواندن source code مرتبط
  → خواندن تست‌های مرتبط
  → اعلام درک
  → تغییر کد
```

این روش هم زمان onboarding را کم می‌کند و هم احتمال برداشت اشتباه از معماری را کاهش می‌دهد.

## مرحله صفر: تعیین نقش و محدودیت Agent

قبل از هر تحلیل، Agent باید مشخص کند:

- درخواست کاربر دقیقاً چیست؟
- آیا فقط تحلیل می‌خواهد یا تغییر کد هم لازم است؟
- کدام بخش‌ها احتمالاً درگیر هستند؟
- چه چیزهایی خارج از scope هستند؟
- آیا داده حساس، token یا اطلاعات خصوصی درگیر است؟

Agent نباید بدون نیاز، کل repository را بازنویسی ذهنی کند یا همه فایل‌ها را بخواند.

## مرحله یک: خواندن اسناد پایه

ابتدا این فایل‌ها را به همین ترتیب بخوان:

1. [README.md](../README.md)
2. [docs/README.md](README.md)
3. [docs/10-ai-agent-handoff.md](10-ai-agent-handoff.md)
4. [docs/11-change-history.md](11-change-history.md)
5. [docs/12-cbm-agent-guide.md](12-cbm-agent-guide.md)

نقش هر فایل:

- `README.md`: هدف کلی و روش اجرای پروژه
- `docs/README.md`: نقشه مستندات و مسیر مطالعه
- `10-ai-agent-handoff.md`: قرارداد handoff و نکات ورود Agent
- `11-change-history.md`: تصمیم‌های معماری و اصلاحات انجام‌شده
- `12-cbm-agent-guide.md`: روش استفاده عملی از CBM

در این مرحله هنوز نباید سراغ خواندن همه source code بروی.

## مرحله دو: استخراج مدل ذهنی اولیه

پس از خواندن مستندات، این موارد را در چند خط بنویس:

```text
Project purpose:
- ...

Main input:
- ...

Main output:
- ...

Main layers:
- ...

Data flow:
- ...

External boundaries:
- ...

Persistence:
- ...

Tests and validation:
- ...

Known constraints:
- ...
```

این مدل اولیه باید از مستندات استخراج شود، نه از حدس‌زدن بر اساس نام فایل‌ها.

## مرحله سه: گرفتن نمای کلی از CBM

از ریشه پروژه اجرا کن:

```bash
CBM="./.tools/codebase-memory-mcp/codebase-memory-mcp"
PROJECT="Local_Lead_Generation_Agents"

"$CBM" --version
"$CBM" cli index_status --project "$PROJECT"
```

اگر پروژه index نشده یا stale است، قبل از ادامه طبق [راهنمای CBM](12-cbm-agent-guide.md) آن را refresh کن.

سپس معماری را بگیر:

```bash
"$CBM" cli get_architecture \
  --project "$PROJECT" \
  --aspects all
```

از خروجی CBM فقط این موارد را در مدل ذهنی وارد کن:

- packageها و layerها
- boundaryهای بین packageها
- hotspotها
- clusterهای اصلی
- تعداد و نوع روابط مهم
- file tree
- parse diagnostics

در این مرحله هدف شناخت **ساختار و مسیرها** است، نه مطالعه جزئیات implementation.

## مرحله چهار: تبدیل درخواست کاربر به محدوده تحلیل

درخواست را به یک یا چند نوع مسئله تبدیل کن:

| نوع مسئله | محدوده اولیه برای بررسی |
|---|---|
| تغییر مدل Lead | `domain`, `results`, تست‌های domain و results |
| تغییر normalization یا dedup | `domain`, storage/repository و تست‌های کیفیت |
| تغییر connector | `connectors`, `apify`, `results` و تست‌های connector |
| تغییر lifecycle اجرا | `service`, `repositories`, `results` و تست‌ها |
| تغییر migration یا schema | `migrations`, `storage`, `repositories` و migration tests |
| تغییر export | `exporters`, CLI و export tests |
| تغییر CLI | `cli`, `config`, `service` و تست‌های مربوط |
| تغییر امنیت یا privacy | مرزهای credential، raw data، export و مستندات privacy |

این جدول فقط نقطه شروع است. محدوده واقعی باید با graph و source تأیید شود.

## مرحله پنج: جست‌وجوی هدفمند در graph

به‌جای بازکردن فایل‌ها، ابتدا symbolها و مسیرهای مرتبط را با CBM پیدا کن:

```bash
"$CBM" cli search_code \
  --project "$PROJECT" \
  --pattern "<symbol-or-concept>" \
  --mode full
```

سپس روابط را بررسی کن:

```bash
"$CBM" cli trace_path \
  --project "$PROJECT" \
  --function-name "<function-or-method>" \
  --direction both \
  --depth 3 \
  --include-tests true
```

از این خروجی یک نقشه کوچک بساز:

```text
Entry point
  → service/use case
  → connector or domain operation
  → repository/storage
  → result/export
  → tests
```

فقط پس از ساختن این نقشه، source code مرتبط را باز کن.

## مرحله شش: خواندن حداقلی و هدفمند source code

اکنون فقط فایل‌هایی را بخوان که حداقل یکی از این شرایط را دارند:

- مستقیماً در trace ظاهر شده‌اند.
- symbol مورد نظر را تعریف می‌کنند.
- caller یا callee مستقیم هستند.
- تست مرتبط دارند.
- مرز امنیتی یا persistence تغییر را لمس می‌کنند.

برای هر فایل این موارد را ثبت کن:

```text
File:
Purpose:
Relevant symbols:
Inputs:
Outputs:
Side effects:
Dependencies:
Compatibility constraints:
Related tests:
```

Agent نباید برای فهم یک تغییر کوچک، تمام فایل‌های `src/` را پشت سر هم بخواند.

## مرحله هفت: اعتبارسنجی با تست و مستندات

بعد از خواندن source مرتبط:

1. تست‌های مستقیم symbol را بخوان.
2. تست‌های caller یا integration را بررسی کن.
3. قرارداد مستندات را با رفتار کد مقایسه کن.
4. مواردی را که graph نشان نمی‌دهد، به‌عنوان unknown ثبت کن.

اگر graph و source اختلاف داشتند:

- source code واقعی را مرجع implementation قرار بده.
- تست‌ها را برای رفتار قابل‌اعتماد بررسی کن.
- اختلاف را گزارش کن.
- graph را بدون refresh معتبر فرض نکن.

## وضعیت فعلی که Agent باید بداند

پیش از هر تغییر، این baseline را در نظر بگیر:

- checkout رسمی توسعه همین مسیر repository و branch `main` است؛ worktree جداگانه لازم نیست.
- منبع فعال فعلی فقط Apify Places با source=`places` است.
- Campaign پیش‌فرض `general` هنگام initialize دیتابیس ساخته می‌شود و Run هر جست‌وجو به یک Campaign متصل است.
- `campaign create/list/show`، export محدودشده با `--campaign` و ثبت Runهای ناموفق فعال هستند.
- export مسیر خروجی را به‌صورت positional می‌گیرد: `export PATH --format csv|json [--campaign ID] [--db PATH]`.
- آخرین اجرای کامل تست: `79 passed` با `pytest -q`.
- `web`، Instagram، TikTok و YouTube هنوز قابلیت فعال و آمادهٔ استفاده نیستند.
- مرحلهٔ بعدی نقشهٔ راه، کیفیت داده است: deduplication چندمنبعی، normalization کامل‌تر، provenance/evidence و فیلتر quality در export.

## قالب اجباری گزارش درک پروژه

پیش از پیشنهاد یا اجرای تغییر، Agent باید این قالب را تکمیل کند:

```text
Project understanding:
- هدف پروژه: ...
- مسیر اصلی داده: ...
- مرزهای مهم: ...
- بخش مرتبط با درخواست: ...

Documentation evidence:
- ...

CBM evidence:
- architecture: ...
- relevant symbols: ...
- callers/callees: ...
- related tests: ...

Source evidence:
- file and symbol: ...
- behavior: ...

Confirmed facts:
- ...

Inferences:
- ...

Unknowns and risks:
- ...

Planned scope:
- ...
```

تا وقتی این گزارش آماده نشده، Agent نباید تغییر گسترده یا refactor معماری پیشنهاد کند.

## workflow کوتاه برای هر Agent جدید

```bash
# 1. فقط اسناد پایه
read README.md
read docs/README.md
read docs/10-ai-agent-handoff.md
read docs/11-change-history.md
read docs/12-cbm-agent-guide.md

# 2. وضعیت حافظه پروژه
CBM="./.tools/codebase-memory-mcp/codebase-memory-mcp"
PROJECT="Local_Lead_Generation_Agents"
"$CBM" cli index_status --project "$PROJECT"
"$CBM" cli get_architecture --project "$PROJECT" --aspects all

# 3. تعیین محدوده و جست‌وجوی graph
"$CBM" cli search_code --project "$PROJECT" --pattern "<relevant-symbol>" --mode full
"$CBM" cli trace_path --project "$PROJECT" --function-name "<relevant-function>" --direction both --depth 3 --include-tests true

# 4. حالا فقط source و tests مرتبط را بخوان

# 5. پس از تغییر، تست و refresh index را طبق docs/12-cbm-agent-guide.md اجرا کن
```

## کارهایی که Agent نباید انجام دهد

- از اولین قدم شروع به خواندن همه فایل‌های کد نکند.
- بر اساس نام فایل، معماری را حدس نزند.
- خروجی CBM را بدون خواندن source قطعی فرض نکند.
- نبودن یک edge را به‌معنی نبودن dependency نداند.
- بدون تعیین scope، refactor گسترده پیشنهاد ندهد.
- secret، token، دیتابیس یا داده خصوصی را وارد گزارش نکند.
- برای فهم پروژه، `.venv`، `.tools` یا cacheها را index نکند.

## تعریف موفقیت

Agent زمانی پروژه را به‌اندازه کافی فهمیده است که بتواند بدون خواندن کل کد، این موارد را دقیق توضیح دهد:

- پروژه چه مسئله‌ای را حل می‌کند؟
- ورودی از کجا وارد می‌شود و خروجی کجا تولید می‌شود؟
- کدام layerها و packageها درگیر هستند؟
- تغییر موردنظر چه caller، callee، storage و تست‌هایی را تحت‌تأثیر می‌گذارد؟
- کدام بخش‌ها fact قطعی و کدام بخش‌ها inference یا unknown هستند؟

این روش جای source code را نمی‌گیرد؛ فقط تضمین می‌کند source code در زمان درست و به‌صورت هدفمند خوانده شود.
