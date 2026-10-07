# راهنمای کار Agent با codebase-memory-mcp

این سند راهنمای اجباری Agentهایی است که روی پروژه `Local_Lead_Generation_Agents` کار می‌کنند. هدف آن این است که Agent قبل از تصمیم‌گیری، از حافظه ساختاری CBM استفاده کند، خروجی را با کد و تست تأیید کند و دچار توهم درباره معماری یا اثر تغییرات نشود.

## ۱. نقش CBM در پروژه

CBM یک حافظه قابل‌پرس‌وجو از source code، تست‌ها، مستندات و روابط معماری پروژه است. این ابزار می‌تواند فایل‌ها، moduleها، classها، functionها، callerها، importها، تست‌ها، لایه‌ها و مسیرهای graph را نشان دهد.

CBM **منبع حقیقت مطلق نیست** و جایگزین این موارد نمی‌شود:

- خواندن source code مرتبط
- اجرای تست‌ها
- بررسی Git diff
- مستندات معماری و تصمیم‌ها
- بررسی رفتار runtime و روابط dynamic پایتون

قانون اصلی:

> از CBM برای پیدا کردن context استفاده کن؛ نتیجه را با کد و تست تأیید کن؛ سپس تصمیم بگیر.

## ۲. مسیر ثابت ابزار و نام پروژه

Agent باید از ریشه پروژه اجرا شود:

```bash
cd /home/pouria/Projects/Personal/Local_Lead_Generation_Agents

CBM="./.tools/codebase-memory-mcp/codebase-memory-mcp"
PROJECT="Local_Lead_Generation_Agents"
```

قبل از استفاده، وجود و نسخه ابزار را بررسی کن:

```bash
test -x "$CBM"
"$CBM" --version
```

اگر binary وجود نداشت، موفقیت جعلی گزارش نکن. مشکل محیط را گزارش کن و تحلیل را فقط بر اساس کد و مستندات ادامه بده.

## ۳. چرخه اجباری کار Agent

هر Agent باید این چرخه را رعایت کند:

```text
index_status
  → architecture/search
  → trace/query وابستگی
  → خواندن فایل‌های واقعی
  → بررسی تست‌ها و مستندات
  → اعلام درک فعلی
  → تغییر کد با اجازه
  → اجرای تست
  → refresh کردن index
  → بررسی نهایی تغییرات
```

Agent نباید قبل از بررسی index و context مرتبط، یک تابع یا کلاس مهم را تغییر دهد.

## ۴. ورود Agent جدید به پروژه

وقتی Agent برای اولین بار وارد پروژه می‌شود، این دستورات را اجرا کند:

```bash
"$CBM" cli index_status --project "$PROJECT"
"$CBM" cli get_architecture \
  --project "$PROJECT" \
  --aspects all
```

از خروجی architecture این موارد را استخراج کن:

- تعداد nodeها و edgeها
- زبان‌ها و تعداد فایل‌ها
- packageها و layerها
- hotspotها
- boundaryهای بین moduleها
- clusterهای اصلی
- file tree

اگر status یکی از حالت‌های زیر بود، آن را دقیق گزارش کن:

- `ready`: index آماده است.
- `project not found or not indexed`: ابتدا باید index ساخته شود.
- stale یا تغییرکرده: قبل از تحلیل مهم refresh لازم است.
- `parse_partial` یا `parse_unusable` بیشتر از صفر: graph ناقص است.

## ۵. ساخت یا refresh کردن index

فقط وقتی index وجود ندارد یا کد/مستندات مهم تغییر کرده‌اند، index را refresh کن:

```bash
"$CBM" cli index_repository \
  --repo-path . \
  --mode full \
  --name "$PROJECT" \
  --persistence true
```

خروجی موفق باید شامل این مفاهیم باشد:

```text
status: indexed
nodes: <number>
edges: <number>
parse_partial_count: 0
parse_unusable_count: 0
```

CBM باید این مسیرها را عمداً کنار بگذارد:

- `.git/`
- `.venv/`
- `.tools/`
- `.env` و secretها
- دیتابیس‌ها
- cacheها
- exportها و build artifactها

کنار گذاشته‌شدن این فایل‌ها نقص نیست؛ یک الزام امنیتی است.

## ۶. جست‌وجوی symbol یا مفهوم

برای symbol مشخص از `search_code` استفاده کن:

```bash
"$CBM" cli search_code \
  --project "$PROJECT" \
  --pattern "SearchResult" \
  --mode full \
  --limit 50
```

مثال‌های پروژه:

```bash
"$CBM" cli search_code --project "$PROJECT" --pattern "SearchLeadsService" --mode full
"$CBM" cli search_code --project "$PROJECT" --pattern "LeadStore" --mode full
"$CBM" cli search_code --project "$PROJECT" --pattern "dedup_key" --mode full
"$CBM" cli search_code --project "$PROJECT" --pattern "Apify" --mode full
```

بعد از پیدا کردن نتیجه، مسیر فایل و line را مستقیماً بخوان. وجود یک node به‌تنهایی اثبات نمی‌کند که تمام رفتار آن symbol در graph ثبت شده است.

## ۷. trace کردن caller و callee

برای فهمیدن مسیر استفاده از یک function یا method:

```bash
"$CBM" cli trace_path \
  --project "$PROJECT" \
  --function-name "SearchResult" \
  --direction both \
  --depth 3 \
  --include-tests true \
  --include-evidence true
```

معنای direction:

- `inbound`: چه چیزهایی این symbol را صدا می‌زنند.
- `outbound`: این symbol چه چیزهایی را صدا می‌زند.
- `both`: هر دو جهت.

برای تحلیل اثر تغییر، از `both` استفاده کن و سپس callerها، تست‌ها و فایل‌های واقعی را بررسی کن.

نکته: `trace_path` برای function و method دقیق‌تر است. برای class یا concept ابتدا با `search_code` نام qualified یا functionهای مرتبط را پیدا کن.

## ۸. تحلیل معماری

برای snapshot معماری کامل:

```bash
"$CBM" cli get_architecture \
  --project "$PROJECT" \
  --aspects all
```

برای تحلیل محدود یک مسیر:

```bash
"$CBM" cli get_architecture \
  --project "$PROJECT" \
  --path leadgen \
  --aspects overview
```

به این گزارش‌ها توجه کن:

- `boundaries`: مرزهای بین packageها
- `layers`: نقش‌های entry/core/leaf/internal
- `hotspots`: symbolهای پرتکرار
- `clusters`: ناحیه‌های منطقی graph
- `file_tree`: ساختار فیزیکی پروژه

این خروجی برای شناخت معماری است، نه مجوز خودکار برای refactor.

## ۹. query مستقیم graph

برای queryهای خواندنی و محدود می‌توان از `query_graph` استفاده کرد:

```bash
"$CBM" cli query_graph \
  --project "$PROJECT" \
  --query 'MATCH (n) WHERE n.name = "SearchResult" RETURN n' \
  --max-rows 50 \
  --format json
```

Query باید read-only باشد. Agent نباید graph یا index را با query تغییر دهد، مگر اینکه صریحاً برای چنین کاری مجوز گرفته باشد.

## ۱۰. تحلیل تغییرات

بعد از تغییر کد و قبل از commit:

```bash
"$CBM" cli detect_changes \
  --project "$PROJECT" \
  --scope impact \
  --direction both \
  --depth 3 \
  --format json
```

اگر branch پایه و مقایسه مشخص است:

```bash
"$CBM" cli detect_changes \
  --project "$PROJECT" \
  --scope impact \
  --direction both \
  --base-branch main \
  --format json
```

خروجی `detect_changes` را با `git diff` و تست‌های مرتبط مقایسه کن. مقدار صفر به‌تنهایی اثبات نمی‌کند که تغییری بی‌خطر است؛ ممکن است graph رابطه را resolve نکرده باشد.

## ۱۱. بررسی coverage

`check_index_coverage` بدون محدوده اجرا نمی‌شود. باید `paths` یا `scopes` بدهی:

```bash
"$CBM" cli check_index_coverage \
  --project "$PROJECT" \
  --paths '["leadgen","tests","doc"]' \
  --diagnostics full
```

یا:

```bash
"$CBM" cli check_index_coverage \
  --project "$PROJECT" \
  --scopes '["leadgen","tests"]' \
  --diagnostics full
```

خطای `paths or scopes is required` به معنی خراب‌بودن index نیست؛ یعنی محدوده بررسی مشخص نشده است.

## ۱۲. workflow قبل از تغییر کد

مثال: قرار است `SearchResult` تغییر کند.

### گام ۱: وضعیت index

```bash
"$CBM" cli index_status --project "$PROJECT"
```

### گام ۲: جست‌وجو

```bash
"$CBM" cli search_code \
  --project "$PROJECT" \
  --pattern "SearchResult" \
  --mode full
```

### گام ۳: trace

```bash
"$CBM" cli trace_path \
  --project "$PROJECT" \
  --function-name "SearchResult" \
  --direction both \
  --depth 3 \
  --include-tests true
```

### گام ۴: خواندن source و tests

حداقل این مسیرها را بر اساس خروجی واقعی بررسی کن:

```text
leadgen/results.py
leadgen/connectors/base.py
leadgen/connectors/apify_places.py
leadgen/service.py
tests/test_results.py
tests/test_connectors.py
```

### گام ۵: گزارش درک قبل از تغییر

Agent باید پیش از تغییر اعلام کند:

```text
CBM findings:
- ...

Source-code findings:
- ...

Test evidence:
- ...

Inferences:
- ...

Unknowns and risks:
- ...

Planned change:
- ...
```

## ۱۳. workflow بعد از تغییر

پس از تغییر:

```bash
pytest -q
```

سپس index را refresh کن:

```bash
"$CBM" cli index_repository \
  --repo-path . \
  --mode full \
  --name "$PROJECT" \
  --persistence true
```

و اثر تغییر را بررسی کن:

```bash
"$CBM" cli detect_changes \
  --project "$PROJECT" \
  --scope impact \
  --direction both \
  --depth 3 \
  --format json
```

در پایان:

```bash
git diff --check
git status --short
```

## ۱۴. ضدتوهم و تفسیر شواهد

Agent باید یافته‌ها را در چهار دسته گزارش کند:

### Confirmed by CBM

چیزی که مستقیماً در خروجی node، edge، trace یا architecture دیده شده است.

### Confirmed by source code

چیزی که با خواندن فایل واقعی و line مشخص تأیید شده است.

### Inferred

برداشتی که از چند رابطه یا الگوی کد به دست آمده، اما مستقیماً اثبات نشده است.

### Unknown

چیزی که graph یا کد فعلی درباره آن شواهد کافی نمی‌دهد.

قواعد اجباری:

- نبودن caller را مساوی «بدون استفاده بودن» ندان.
- رابطه `SEMANTICALLY_RELATED` یا inference را dependency قطعی اعلام نکن.
- خروجی graph را بدون خواندن source تغییر نده.
- برای رفتار dynamic، registry، dependency injection و reflection احتیاط کن.
- اگر index ناقص یا stale است، نتیجه را قطعی گزارش نکن.
- اگر CBM و کد تناقض داشتند، تناقض را گزارش و source/test را مرجع نهایی قرار بده.

## ۱۵. سناریوهای کاربردی پروژه

### بررسی مسیر جست‌وجو

```bash
"$CBM" cli search_code --project "$PROJECT" --pattern "SearchLeadsService" --mode full
"$CBM" cli trace_path --project "$PROJECT" --function-name "search" --direction both --depth 4 --include-tests true
```

سپس این مسیر را با کد تأیید کن:

```text
leadgen/cli.py → leadgen/service.py → leadgen/registry.py
→ leadgen/connectors/apify_places.py → leadgen/storage.py
```

### بررسی deduplication

```bash
"$CBM" cli search_code --project "$PROJECT" --pattern "dedup_key" --mode full
"$CBM" cli search_code --project "$PROJECT" --pattern "upsert" --mode full
```

### بررسی migration

```bash
"$CBM" cli search_code --project "$PROJECT" --pattern "migrate" --mode full
"$CBM" cli trace_path --project "$PROJECT" --function-name "migrate" --direction both --depth 3 --include-tests true
```

### بررسی export

```bash
"$CBM" cli search_code --project "$PROJECT" --pattern "export_csv" --mode full
"$CBM" cli search_code --project "$PROJECT" --pattern "formula" --mode full
```

## ۱۶. خطاهای رایج

### پروژه index نشده است

```text
project not found or not indexed
```

راه‌حل:

```bash
"$CBM" cli index_repository --repo-path . --mode full --name "$PROJECT" --persistence true
```

### coverage بدون محدوده اجرا شده است

```text
paths or scopes is required
```

راه‌حل: `--paths` یا `--scopes` اضافه کن.

### binary پیدا نمی‌شود

راه‌حل: از ریشه پروژه اجرا کن و بررسی کن:

```bash
test -x "$CBM"
"$CBM" --version
```

### index stale است

راه‌حل: بعد از اطمینان از root درست، `index_repository` را دوباره اجرا کن.

### parser خطا داده است

اگر `parse_partial_count` یا `parse_unusable_count` بیشتر از صفر بود، محدوده ناقص است و باید این محدودیت در گزارش نهایی ذکر شود.

## ۱۷. چک‌لیست سریع Agent

```text
[ ] از ریشه پروژه کار می‌کنم.
[ ] CBM binary و نسخه را بررسی کردم.
[ ] index_status را اجرا کردم.
[ ] برای سؤال معماری get_architecture گرفتم.
[ ] برای symbol موردنظر search_code اجرا کردم.
[ ] caller/callee مرتبط را trace کردم.
[ ] source code و tests را خواندم.
[ ] یافته‌های CBM و source را جدا گزارش کردم.
[ ] بعد از تغییر pytest -q اجرا کردم.
[ ] index را refresh کردم.
[ ] detect_changes را اجرا کردم.
[ ] git diff --check و git status را بررسی کردم.
```

## جمع‌بندی

CBM کمک می‌کند Agent مجبور نباشد هر بار کل پروژه را از صفر بخواند؛ اما Agent مسئول تأیید شواهد است. بهترین استفاده از CBM این است:

```text
Graph context
  + source code
  + tests
  + documentation
  + Git diff
  = تصمیم قابل اعتمادتر
```
