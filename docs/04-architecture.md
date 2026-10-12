# معماری

## معماری فعلی — 2026-10-12

این نمودار وضعیت اجرایی فعلی را نشان می‌دهد، نه قابلیت‌های تاریخی. فقط `places` و جست‌وجوی مستقل `instagram` فعال‌اند و هر درخواست دقیقاً یک منبع انتخاب می‌کند. Google Search، LinkedIn، TikTok، YouTube و enrichment چندمنبعی جزو محصول فعال نیستند.

Instagram فقط در حالت standard با `liveSearch=false` و enhancement غیرفعال اجرا می‌شود: یک عبارت بدون ویرگول، limit پیش‌فرض ۱۰ و بازهٔ ۱ تا ۲۵۰. Campaign اینستاگرام باید صریحاً انتخاب شود و با Campaign لیدهای Places مشترک نیست. نتیجهٔ جست‌وجو تضمین جغرافیایی یا تأیید کسب‌وکار نیست.

## نمودار اجزا و جریان داده

```mermaid
flowchart TB
    USER["کاربر"] --> CLI["CLI<br/>Places / Instagram / Campaign / Export / Jobs"]
    USER --> WEB["FastAPI + Jinja<br/>پنل محلی فارسی و RTL"]
    SETTINGS["Settings<br/>Environment / Apify token"] --> SERVICE["SearchLeadsService"]
    CLI --> SERVICE
    WEB --> SERVICE
    CLI --> JOBS["JobService / JobRepository<br/>submit / status / retry / cancel / review"]
    WEB --> JOBS
    JOBS --> JOBTABLE[(jobs)]
    WCLI["CLI Worker"] --> WORKER["JobWorker<br/>atomic claim / fencing / heartbeat"]
    JOBTABLE --> WORKER
    WORKER --> HANDLER["Handler<br/>یک منبع برای هر درخواست"]
    HANDLER --> SERVICE
    WORKER --> CACHE["ExecutionCache<br/>versioned persisted references"]
    WORKER --> BUDGET["BudgetRepository<br/>reservation / reconciliation"]
    WORKER --> ATTEMPTS["Provider attempts<br/>resume / cancellation / needs_review"]
    SERVICE --> REQUEST["Source-specific request validation<br/>Places location / Instagram phrase and campaign"]
    REQUEST --> REG["ConnectorRegistry<br/>places / instagram"]
    REG --> PLACES["ApifyPlacesConnector"]
    REG --> INSTAGRAM["InstagramDiscoveryConnector"]
    PLACES --> API["ApifyClient<br/>header auth / timeout / retry / run lifecycle"]
    INSTAGRAM --> API
    API --> PA["compass~crawler-google-places"]
    API --> IA["apify~instagram-search-scraper<br/>standard-only"]
    PA --> DATASET["Dataset / provider status"]
    IA --> DATASET
    DATASET --> RESULT["SearchResult<br/>counts / warnings / projections / provenance"]
    RESULT --> STORE["LeadStore<br/>source-specific transactional persistence"]
    STORE --> LEADREPO["LeadRepository / QualityRepository<br/>normalization / scoring / identity"]
    STORE --> IGREPO["InstagramCampaignRepository<br/>validated public profile observations"]
    LEADREPO --> LEADDB["SQLite Places tables<br/>leads / campaigns / campaign_leads<br/>runs / raw_records / observations / field_evidence"]
    IGREPO --> IGDB["SQLite Instagram tables<br/>instagram_campaigns / instagram_campaign_runs<br/>instagram_profile_observations"]
    LEADDB --> LEXPORT["Lead JSON / CSV<br/>global or Places campaign"]
    IGDB --> IEXPORT["Instagram campaign JSON / CSV<br/>latest valid profile observations"]
    RESULT --> REXPORT["Source-specific run export / reload<br/>historical runs remain accessible"]
    MAINT["Maintenance / Backup / Restore<br/>controlled local helpers"] --> LEADDB
    MAINT --> IGDB
    PRIV["Privacy boundary<br/>public profiles / safe links / raw allowlist<br/>no inferred contacts or ownership"] -.-> RESULT
```

همهٔ جدول‌های نمایش‌داده‌شده در یک SQLite محلی نگهداری می‌شوند؛ جداسازی در نمودار **منطقی** است، نه دو دیتابیس یا دو سرویس مستقل. CLI مستقیماً از service استفاده می‌کند؛ API وب واسطهٔ اجباری CLI نیست. ثبت Job نیز به‌تنهایی Worker ایجاد یا اجرا نمی‌کند.

## منطق ذخیره‌سازی و خروجی

```mermaid
flowchart TB
    RESULT["نتیجهٔ منبع"] --> SOURCE{"منبع درخواست"}
    SOURCE --> P["Places"]
    SOURCE --> I["Instagram"]
    P --> PS["Lead upsert + identity + observations<br/>Campaign membership by lead_id"]
    I --> IS["Explicit Instagram campaign<br/>atomic run payload + profile observations"]
    PS --> PE["Lead export"]
    IS --> HISTORY["Campaign run history<br/>failed or empty runs do not erase profiles"]
    HISTORY --> AGG["Latest valid observations<br/>provider ID first / canonical username fallback"]
    AGG --> IE["Instagram profile export<br/>Unicode JSON / UTF-8 BOM CSV"]
    HIST["Historical Instagram runs"] --> RE["Run-specific export"]
    HIST -.-> NOIMPORT["No automatic import into new campaigns"]
```

- Places و Instagram schema خروجی مستقل دارند؛ پروفایل Instagram به Lead کسب‌وکار تبدیل یا با آن ادغام نمی‌شود.
- هویت پروفایل ابتدا بر مبنای provider ID و سپس username canonical است؛ جدیدترین observation معتبر با ترتیب `(started_at, run_id)` انتخاب می‌شود.
- Run موفق replay‌شده نمی‌تواند به Campaign دیگری منتقل شود؛ Runهای failed/empty در تاریخچه باقی می‌مانند و پروفایل‌های قبلی را حذف نمی‌کنند.
- دادهٔ Instagram شامل فیلدهای عمومی پروفایل و لینک‌های امن است؛ از biography شماره تماس یا مالکیت استنتاج نمی‌شود.
- CSV از formula injection محافظت می‌شود. ذخیرهٔ تاریخی به معنی فعال‌بودن sourceهای حذف‌شده نیست.

## اجرا و محدودیت‌ها

- Worker از claim اتمیک، fencing، heartbeat، provider attempt و resume استفاده می‌کند. نتیجهٔ نامعلوم provider می‌تواند به `needs_review` نیاز داشته باشد؛ این سازوکار تضمین عمومی exactly-once در سرویس خارجی نیست.
- Cache، budget و maintenance اجزای داخلی محلی‌اند؛ در نمودار queue خارجی یا daemon خودکار فرض نشده است.
- authentication و دسترسی شبکه‌ای از این نمودار نتیجه نمی‌شوند؛ پنل برای اجرای محلی طراحی شده است.
- اجرای پولی Actor و certification حالت live در این به‌روزرسانی انجام نشده است.

## مراجع implementation

- [Registry](../src/registry.py)، [Service](../src/service.py) و [Request models](../src/search_requests.py)
- [Connectorها](../src/connectors/)، [Apify client](../src/apify.py) و [Execution](../src/execution/)
- [Storage](../src/storage.py)، [Instagram campaigns](../src/instagram_campaigns.py) و [Migrations](../src/migrations.py)
- [عملیات](02-operations-guide.md)، [مدل داده](05-data-model.md) و [قرارداد Apify](06-apify-integration.md)
