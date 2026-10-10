# Remaining Lead Generation Phases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after explicit user approval. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** تکمیل کیفیت داده، منابع تکمیلی، تطبیق پروفایل، اجرای پایدار پس‌زمینه و رابط وب پیشرفته، بدون شکستن CLI، Campaignها و export فعلی.

**Architecture:** هستهٔ فعلی Python/SQLite حفظ می‌شود. discovery کسب‌وکار از enrichment کسب‌وکار شناخته‌شده جدا می‌شود؛ مشاهده‌های منبع به هویت پایدار Lead و evidence قابل حسابرسی متصل می‌شوند. UI از application service استفاده می‌کند و اجرای طولانی پس از آماده‌شدن زیرساخت هزینه و lifecycle به worker مستقل منتقل می‌شود.

**Tech Stack:** Python >=3.10، Pydantic 2، SQLite، HTTPX، Typer، FastAPI، Jinja2، pytest و respx؛ افزودن ابزار تازه فقط با نیاز اثبات‌شده و تغییر manifest.

## Global Constraints

- وضعیت: **فقط پلن؛ اجرای هیچ task مجاز نیست تا کاربر صریحاً تأیید کند.**
- مرجع پایه: schema نسخهٔ 2، منبع فعال `places`، suite گزارش‌شدهٔ 89 تست؛ تعداد تست هدف ثابت نیست.
- `leadgen` و `python -m src.cli`، Campaign پیش‌فرض `general` و export پیش‌فرض JSON/CSV سازگار بمانند.
- `source=web` اکنون disabled است؛ «رابط وب فعال» با «منبع web غیرفعال» یکی نیست.
- `APIFY_API_TOKEN` فقط در environment و Authorization header؛ نه URL، HTML، دیتابیس، fixture، log یا export.
- فقط اطلاعات عمومی حرفه‌ای با ارتباط روشن به کسب‌وکار؛ reviewer/person extraction و استنتاج مالکیت ممنوع.
- فقط localhost تا تکمیل و تأیید دروازهٔ انتشار؛ هیچ reverse proxy یا bind عمومی به‌طور ضمنی اضافه نشود.
- تست خودکار آفلاین؛ اجرای پولی Actor فقط با تأیید مستقل و سقف کم.
- هر migration روی کپی دیتابیس تست شود؛ هیچ دادهٔ واقعی برای fixture یا graph استفاده نشود.
- مقادیر threshold در این پلن سیاست اولیهٔ محافظه‌کارانه‌اند، نه confidence آماری کالیبره‌شده.
- هر task مستقل commit شود؛ commit فقط هنگام اجرا و با trailer استاندارد پروژه. خود پلن اکنون commit نمی‌شود.

---

## 1. مبنای واقعی و حدود این سند

کد بررسی‌شده: `src/domain.py`, `src/service.py`, `src/storage.py`, `src/migrations.py`, `src/results.py`, `src/registry.py`, `src/connectors/base.py`, `src/web/routes.py` و manifest.

- `Lead.dedup_key()` ترکیب name/address/phone است و primary key جدول leads و FK عضویت Campaign به آن وابسته‌اند.
- `identity_candidates` و matching پایه وجود دارند؛ persistence فعلی همچنان از dedup key استفاده می‌کند. وجود helper به معنی dedup کامل چندمنبعی نیست.
- `SearchLeadsService.search(query, location, source, limit, campaign_id)` هم orchestration و هم persistence را انجام می‌دهد.
- `SearchResult` lifecycle و منع Lead در failure را enforce می‌کند؛ این قرارداد حفظ می‌شود.
- Connector discovery امضای `search(query, location, limit) -> SearchResult` دارد؛ SocialConnector فعلی stub غیرفعال است.
- Run فعلی و Job آینده دو مفهوم متفاوت‌اند: یک Job می‌تواند چند Run منبع داشته باشد.
- CBM در بررسی فعلی ready با 668 node و 2233 edge بود؛ graph جای خواندن source مربوط را نمی‌گیرد.
- handoff هنوز baseline 79 را ذکر می‌کند؛ اصلاح این اختلاف در اولین task اجرایی است، نه در این درخواستِ صرفاً پلن.

این سند master plan مهندسی است. schema و mapping Actorهای هنوز فعال‌نشده در task مربوط با مستندات رسمی همان زمان تثبیت می‌شوند؛ نام fieldهای Actor حدس زده نمی‌شوند. هر منبع تا عبور از contract gate غیرفعال باقی می‌ماند.

## 2. ترتیب اجرا و وابستگی‌ها

```text
A: identity + observations + matching + export quality
  ├── B: execution lifecycle + budget + persistent jobs
  └── C: Google Search discovery/enrichment
          └── D: profile evidence/review
                 └── E1 Instagram / E2 YouTube / E3 TikTok
B + C + D + E approved sources → F: multi-source orchestration
A + B → G: advanced local UI + Run history
G → H: optional team access and controlled deployment
F + G → I: CRM export + operational hardening
```

B و C فقط پس از تثبیت قراردادهای A قابل موازی‌سازی‌اند. Adapterهای اجتماعی پس از D مستقل‌اند؛ SQLite migrationها و فایل‌های مشترک registry/service نباید هم‌زمان توسط چند implementer ویرایش شوند.

| فاز | خروجی مستقل | وابستگی | شرط خروج |
|---|---|---|---|
| A | Lead پایدار و دادهٔ قابل حسابرسی | موجود | migration، matching و export سازگار |
| B | اجرای محلی پایدار و کنترل هزینه | A | recovery بدون شروع کورِ Actor دوم |
| C | Google Search کنترل‌شده | A، contract gate | evidence معتبر و تست adapter |
| D | اتصال/review پروفایل | A+C | عدم نسبت‌دادن حساب نامرتبط |
| E | adapterهای اجتماعی | D، contract gate هر Actor | allowlist و failure مستقل |
| F | pipeline چندمنبعی | B+C+D+منابع تأییدشده E | partial success و budget صحیح |
| G | پنل پیشرفتهٔ محلی | A+B | job، history، filters و review |
| H | دسترسی تیمی اختیاری | G، تصمیم مقصد | auth، authorization و انتشار امن |
| I | CRM و سخت‌سازی | F+G | export نسخه‌دار و runbook بازیابی |

برآورد اولیه: A حدود 6–10، B حدود 7–12، C حدود 3–5، D حدود 4–7، هر adapter اجتماعی حدود 3–5، F حدود 4–7، G حدود 5–9، H تیمی حدود 6–12 و I حدود 4–7 روز کاری توسعه/بازبینی. این‌ها تضمین نیستند؛ schema Actor، حجم داده و مقصد deployment باید قبل از تعهد زمانی بررسی شوند.

## 3. مرزبندی فایل‌ها و قراردادها

فایل‌های زیر **پیشنهادی برای زمان اجرا** هستند؛ اکنون ساخته نمی‌شوند.

| مسیر | مسئولیت |
|---|---|
| `src/quality/models.py` | Observation، Evidence، MatchDecision و QualityMetrics |
| `src/quality/normalization.py` | کلیدهای canonical؛ حفظ مقدار نمایش و متن اصلی مجاز |
| `src/quality/matching.py` | قواعد هویت/branch-aware؛ بدون SQL و شبکه |
| `src/quality/service.py` | ingest، merge و انتخاب مقدار با provenance |
| `src/quality/repository.py` | CRUD observation/identity/evidence روی connection تزریق‌شده |
| `src/execution/models.py` | Job، Step، Attempt، budget و state machine |
| `src/execution/repository.py` | claim اتمیک، lease، checkpoint و idempotency |
| `src/execution/service.py` | enqueue/status/cancel/retry؛ بدون thread در request |
| `src/execution/worker.py` | worker مستقل، heartbeat و recovery |
| `src/execution/budget.py` | reserve/reconcile؛ currency یکسان و Decimal |
| `src/enrichment/models.py` | EnrichmentRequest/Result و ProfileCandidate |
| `src/enrichment/service.py` | enrichment روی Lead مشخص و evidence |
| `src/enrichment/repository.py` | profile candidates و review audit |
| `src/connectors/google_search.py` | تکمیل adapter موجود و غیرفعال Google Search |
| `src/connectors/instagram.py`, `youtube.py`, `tiktok.py` | adapter جدا برای هر منبع |
| `src/pipeline.py` | برنامهٔ اجرای چندمنبعی و وابستگی stepها |
| `src/web/job_routes.py`, `lead_routes.py`, `run_routes.py` | routeهای متمرکز؛ service-only |
| `src/web/auth.py` | فقط در فاز H: session و authorization |
| `src/crm_export.py` | mapping نسخه‌دار CSV/JSON؛ بدون push به CRM |

فایل‌های موجود `domain.py`, `migrations.py`, `storage.py`, `repositories.py`, `service.py`, `apify.py`, `registry.py`, `config.py`, `cli.py`, `exporters.py` فقط در taskهای لازم تغییر می‌کنند. facade `LeadStore` حفظ می‌شود؛ تقسیم repositoryهای موجود فقط وقتی به task مرتبط لازم باشد.

### قراردادهای جدید مورد اتکا

```python
# قرارداد پیشنهادی؛ همهٔ مدل‌ها Pydantic و زمان‌ها UTC-aware هستند.
Observation = {observation_id, lead_id, source, source_record_id,
               source_url, run_id, collected_at, fields, mapper_version}
Evidence = {field, value, source_url, observation_id, collected_at,
            evidence_kind, confidence, policy_version}
MatchDecision = {action: "merge" | "review" | "separate",
                 candidate_lead_id: str | None, confidence: float,
                 reasons: tuple[str, ...], policy_version: str}
QualityMetrics = {completeness: float, identity_confidence: float | None,
                  field_confidence: dict[str, float], popularity: float,
                  policy_version: str}
EnrichmentRequest = {lead_id, source, candidate_urls: tuple[str, ...],
                     campaign_id, limit, correlation_id}
EnrichmentResult = {observations, profile_candidates, run_metadata, warnings}
```

امضاهای مرزی که در task خود تعریف و سپس مصرف می‌شوند:

```python
canonicalize(lead: Lead, country_code: str | None = None) -> CanonicalLead
match(incoming: CanonicalLead, candidates: list[CanonicalLead]) -> MatchDecision
ingest(result: SearchResult, campaign_id: str) -> IngestionSummary
enrich(request: EnrichmentRequest) -> EnrichmentResult
submit(request: JobRequest, idempotency_key: str) -> Job
claim(worker_id: str, now: datetime, lease_seconds: int) -> Job | None
reserve(job_id: str, step_id: str, amount: Decimal, currency: str) -> Reservation
```

`CanonicalLead` شامل lead_id اختیاری، نام/تلفن/دامنه/آدرس canonical، source/source_id و country_code است. `IngestionSummary` شامل شمارنده‌های inserted/updated/merged/review/separate و mapping observation به lead_id است. `JobRequest` شامل campaign_id/query/location/sources/limit/max_cost/currency/policy_version است. `Job` شناسه، state، progress، timestamps و error_code امن دارد؛ `Reservation` مبلغ، currency، step_id و state دارد. جزئیات داخلی این مدل‌ها پیش از اولین consumer در تست producer تثبیت می‌شوند.

## 4. الگوی اجرا و بازبینی هر task

هر task پایین این چرخه را دارد؛ هیچ task صرفاً scaffolding نیست:

- [ ] تست پذیرش‌های نام‌برده با fixture ساختگی و API عمومی همان task نوشته شود.
- [ ] همان selector اجرا شود و failure به نبود رفتار هدف مرتبط باشد، نه missing dependency.
- [ ] producer و migration/adapter لازم پیاده شود؛ consumerها در task وابسته اضافه شوند.
- [ ] selectorهای مرتبط در یک اجرای pytest سبز شوند؛ قراردادهای قدیمی پوشش داده شوند.
- [ ] doc مستقیم، failure behavior و compatibility impact ثبت شود.
- [ ] `git diff --check` و بازبینی diff انجام شود؛ سپس commit محدود همان task.

دستور پایه برای selectorهای جدول‌ها: `PYTHONPATH=. .venv/bin/pytest -q <selectors>`.
در پایان هر فاز، suite کامل برای gate سازگاری اجرا شود؛ تغییر doc-only به اجرای آزمون نیاز ندارد. commitها conventional و با `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>` هستند.

## 5. فاز A — کیفیت داده و هویت پایدار

### A1. مدل observation و migration هویت

**Files:** ایجاد `src/quality/models.py`, `src/quality/repository.py`؛ تغییر `src/domain.py`, `src/migrations.py`, `src/repositories.py`, `src/storage.py`؛ تست `tests/test_quality_migrations.py` و `tests/test_migrations.py`.

**Produces:** lead_id پایدار UUID مستقل از دادهٔ mutable و CRUD observation؛ هنوز auto-merge تاریخی اجرا نمی‌شود.

- [ ] schema نسخهٔ 3: جدول leads دارای lead_id PK؛ جدول mapping legacy dedup_key به lead_id؛ membership به lead_id بازسازی شود.
- [ ] unique identity فقط روی `(source, source_record_id)` غیرخالی؛ تلفن/دامنه unique نباشند چون مشترک بین شعب‌اند.
- [ ] observation append-only و field evidence با FK به Lead و Run؛ payload فقط allowlist.
- [ ] backfill هر Lead قدیمی با ID مستقل؛ Run، payload، timestamps و Campaignهایش بدون کاهش تعداد حفظ شوند.
- [ ] دادهٔ بدون source_url یا provenance قدیمی با `legacy_import` و confidence نامعلوم ثبت شود؛ زمان/منبع ساختگی تولید نشود.
- [ ] recovery: backup با SQLite backup API؛ شکست migration کل transaction را rollback کند. برگشت به نسخهٔ کد قبلی فقط با restore backup، نه downgrade مخرب.

**Tests:** `test_migrate_v2_preserves_payloads_and_campaign_links`, `test_migration_is_idempotent`, `test_migration_failure_rolls_back`, `test_phone_change_keeps_lead_id`, `test_legacy_missing_evidence_is_unknown`.
**Gate:** fixture v2 و fresh DB یک schema بدهند؛ FK check سالم؛ default export همان محتوا/fields قبلی.
**Docs:** `docs/05-data-model.md`, `docs/10-ai-agent-handoff.md`, `docs/11-change-history.md`؛ baseline stale اصلاح شود.

### A2. normalization و matching branch-aware

**Files:** ایجاد `src/quality/normalization.py`, `matching.py`؛ تغییر helpers مرتبط `src/domain.py`؛ تست `tests/test_quality_matching.py`, `tests/test_domain_quality.py`.
**Consumes:** CanonicalLead و identity lookup از A1. **Produces:** MatchDecision با policy نسخهٔ `identity-v1`.

- [ ] ارقام فارسی/عربی و ی/ک عربی فقط در canonical search key یکسان شوند؛ نام نمایشی مخرب تغییر نکند.
- [ ] تلفن با country context نرمال شود؛ شمارهٔ مبهم بدون فرض ایران به E.164 تبدیل نشود.
- [ ] دامنه با host canonical مقایسه شود؛ query مربوط به شناسایی پروفایل کورکورانه حذف نشود.
- [ ] ID پایدار همان source: merge؛ هویت معتبر متناقض/شعبه متفاوت: separate یا review، نه overwrite.
- [ ] دو evidence مستقل قوی بدون تضاد: merge با rule confidence 0.95؛ یک تلفن یا یک دامنه مشترک: review با 0.70؛ نام تنها: separate.
- [ ] conflicting branch/address با source IDهای متفاوت حتی با دامنه یکسان auto-merge نشود.
- [ ] تصمیم threshold مستند و قابل بازتولید؛ confidence مقدار احتمال علمی ادعا نشود.

**Tests:** `test_same_provider_id_matches`, `test_shared_domain_branches_not_merged`, `test_shared_phone_needs_review`, `test_persian_name_variants`, `test_missing_country_not_guessed`, `test_conflicting_identity_not_overwritten`.
**Gate:** false positive صفر روی مجموعهٔ fixtureهای صریح شعب/هم‌نام؛ false negative شناخته‌شده گزارش شود.

### A3. ingest تراکنشی، evidence و merge قابل بازبینی

**Files:** ایجاد `src/quality/service.py`؛ تغییر `src/storage.py`, `src/service.py`؛ تست `tests/test_quality_ingestion.py`, `tests/test_campaigns.py`, `tests/test_search_failures.py`.
**Consumes:** A1+A2. **Produces:** ingest و review decisions.

- [ ] service همان امضای search را حفظ کند و persistence را از طریق ingest اجرا کند.
- [ ] انتخاب مقدار: مقدار empty هیچ مقدار معتبر را حذف نکند؛ تضاد observation حفظ و انتخاب canonical همراه reason ذخیره شود.
- [ ] ID source یکسان با مشاهده جدید: update Lead ثابت و append observation؛ replay دقیق همان Run/record دوباره observation نسازد.
- [ ] merge تنها با انتقال membership همهٔ Campaignها، identityها و evidence در یک transaction؛ merged_id alias/redirect و audit داشته باشد.
- [ ] human review: accept/reject با reviewer/action/time؛ undo merge با provenance membership و تغییرات بعدی کنترل شود. در تعارض جدید undo به review برود، نه split خودکار.
- [ ] failed Run هیچ Lead/raw تولید نکند؛ partial فقط دادهٔ معتبر مشاهده‌شده را با warning نگه دارد.

**Tests:** `test_merge_preserves_all_campaign_memberships`, `test_replay_is_idempotent`, `test_empty_value_does_not_erase_evidence`, `test_failed_ingestion_is_atomic`, `test_manual_merge_audited`, `test_undo_conflict_requires_review`.
**Gate:** یک کسب‌وکار با تغییر شماره هویت ثابت بماند؛ تکرار ingest شمارنده‌ها/observations را تکثیر نکند.

### A4. metrics و export فیلترشدهٔ سازگار

**Files:** تغییر `src/exporters.py`, `src/storage.py`, `src/cli.py`؛ مدل metrics در `src/quality/models.py`؛ تست `tests/test_quality_exports.py`, `tests/test_campaign_exports.py`.

- [ ] legacy score حفظ شود؛ completeness/identity_confidence/field_confidence جدا و versioned باشند.
- [ ] completeness جدید 0–100 با وزن name=15/address=25/phone=25/website=25/category=10؛ availability با truth/confidence یکی نباشد.
- [ ] `--min-completeness`, `--has-phone`, `--has-website`, `--extended` optional؛ نبود فیلتر همان رفتار قبلی.
- [ ] pagination یا iterator قبل از export؛ عدم load کامل مجموعهٔ لیدها؛ CSV formula escaping حفظ شود.
- [ ] extended شامل lead_id، quality و evidence summary باشد؛ raw payload و token هرگز صادر نشوند.

**Tests:** `test_default_export_contract_unchanged`, `test_quality_filters_combine_with_campaign`, `test_confidence_unknown_is_not_zero`, `test_empty_csv_headers_stable`, `test_extended_excludes_secrets`.
**Gate A:** suite کامل، migration report، نمونهٔ synthetic legacy/default/extended و review سیاست matching برای تأیید.

## 6. فاز B — execution، بودجه و jobs پایدار

### B1. lifecycle Actor قابل checkpoint

**Files:** تغییر `src/apify.py`, `src/connectors/apify_places.py`, `src/results.py`, `src/service.py`؛ تست `tests/test_apify_lifecycle.py`, `tests/test_apify_client.py`.
**Produces:** عملیات start/poll/read/abort جدا و sync wrapper سازگار.

- [ ] provider run ID به‌محض دریافت پایدار شود؛ poll/read retry امن از start جدا شود.
- [ ] timeout پاسخ start: start مجدد خودکار ممنوع؛ attempt حالت `start_unknown` بگیرد تا reconciliation یا تصمیم دستی.
- [ ] pagination dataset با checkpoint و ingestion chunkهای bounded؛ failure وسط dataset با status partial و evidence مشخص.
- [ ] redaction مرکزی error_code/message امن و correlation_id؛ token check برای تمام sourceهای enabled نه فقط places.
- [ ] cancel provider best-effort باشد؛ درخواست cancel مساوی تأیید abort نیست.

**Tests:** `test_start_timeout_does_not_blindly_restart`, `test_resume_known_provider_run`, `test_paginated_read_checkpoint`, `test_cancel_pending_provider_confirmation`, `test_credentials_redacted_for_all_sources`.

### B2. budget و rate limit

**Files:** ایجاد `src/execution/budget.py`, `models.py`, `repository.py`؛ تغییر `src/config.py`, `src/migrations.py`؛ تست `tests/test_budget.py`.
**Produces:** reserve/reconcile و rate policy پیش از هر remote start.

- [ ] migration بعد از A1 شامل reservations و attempt metadata؛ ترتیب نسخه‌ها در execution تثبیت شود.
- [ ] max_cost و currency صریح؛ Decimal و integer minor units؛ estimate، reserved و actual سه مقدار جدا.
- [ ] reservation اتمیک و مشترک بین CLI و worker؛ over-budget رد شود؛ policy/pricing version ذخیره شود.
- [ ] اگر Actor سقف provider-supported ندارد، سقف محلی ضمانت هزینهٔ واقعی نیست؛ نمایش best-effort و مسدودسازی اجرای unattended پرهزینه.
- [ ] هزینه نامعلوم reservation را آزاد نکند؛ تا reconciliation نگه دارد. Actor پولی متوقف‌شده نیز ممکن است هزینه داشته باشد.
- [ ] 429 با Retry-After/backoff محدود؛ concurrency شروع اولیه یک Actor برای account محلی.

**Tests:** `test_atomic_reservation_prevents_overspend`, `test_unknown_cost_keeps_reservation`, `test_currency_mismatch_rejected`, `test_retry_after_respected`, `test_no_budget_bypass_from_cli`.

### B3. durable queue، worker و cache

**Files:** ایجاد `src/execution/service.py`, `worker.py`؛ تغییر `src/cli.py`, `src/storage.py`, `src/config.py`, `src/migrations.py`؛ تست `tests/test_jobs.py`, `tests/test_worker_recovery.py`.
**Consumes:** B1+B2. **Produces:** submit/claim/status/cancel/retry.

- [ ] SQLite queue ابتدا یک worker مستقل؛ WAL/busy_timeout و transaction کوتاه؛ تماس شبکه بیرون transaction.
- [ ] claim با شرط state و lease در transaction؛ heartbeat، lease expiry، fencing token برای جلوگیری از completion توسط worker قدیمی.
- [ ] states: queued/running/cancel_requested/succeeded/partial/failed/cancelled/needs_review؛ progress stepهای تمام‌شده، نه درصد ساختگی Actor.
- [ ] unique idempotency key از request کاربر؛ fingerprint جدا شامل source/input/Actor build/mapper/policy/country/campaign context.
- [ ] retry فقط step امن؛ completion و persistence idempotent. guarantee برابر at-least-once local processing، نه exactly-once provider start.
- [ ] cache opt-in با TTL اولیه 24 ساعت و force-refresh؛ reuse به‌عنوان cached observation با collected_at اصلی، نه دادهٔ تازه.
- [ ] worker shutdown cooperative؛ Run درحال اجرا روی recovery با provider ID ادامه یابد؛ start_unknown به needs_review برود.
- [ ] CLI فعلی synchronous باقی بماند و از policy مشترک عبور کند؛ `leadgen jobs submit/status/cancel` و `leadgen worker` افزوده شوند.

**Tests:** `test_two_workers_claim_once`, `test_expired_lease_fenced`, `test_crash_after_remote_start_recovers`, `test_duplicate_submission_returns_same_job`, `test_cache_preserves_collection_time`, `test_cancel_does_not_report_false_success`.
**Gate B:** kill/restart worker آزمایشی با mock provider، بدون duplicate ingestion یا شروع کور Actor؛ runbook recovery نوشته شود.

## 7. فاز C — Google Search

### C1. contract gate و discovery adapter

**Files:** تغییر `src/connectors/google_search.py`, `src/registry.py`, `src/config.py`؛ fixtures در `tests/fixtures/google_search/`؛ تست `tests/test_google_search.py`.
**Consumes:** A، lifecycle B1 برای checkpoint در job mode. **Produces:** source `web` با Actor `apify~google-search-scraper` تنها پس از gate.

- [ ] schema ورودی/خروجی، build/version، pagination، pricing و limit واقعی از مستندات رسمی بررسی و در `docs/06-apify-integration.md` ثبت شوند.
- [ ] discovery خروجی result URL/title/snippet را evidence candidate بداند؛ snippet مالک یا نشانی قطعی تلقی نشود.
- [ ] عبارت شغل+شهر به شکل deterministic ساخته شود؛ limit قبل از هزینه constrain شود.
- [ ] registry و UI enabled sources از یک capability descriptor بخوانند؛ `web` تا PASS تست contract disabled بماند.
- [ ] schema drift کل adapter را fail-safe کند؛ malformed item از نتیجه حذف با count warning، malformed کل response خطای ساختاریافته.

**Tests:** `test_actor_request_matches_verified_schema`, `test_serp_items_are_candidates_not_confirmed_owners`, `test_result_limits`, `test_empty_result_lifecycle`, `test_disabled_until_contract_gate`, `test_no_token_in_request_url`.

### C2. enrichment وب‌سایت و business-specific search

**Files:** ایجاد `src/enrichment/models.py`, `service.py`؛ تغییر adapter Google Search؛ تست `tests/test_web_enrichment.py`.
**Produces:** EnrichmentRequest/Result و candidate evidence برای Lead مشخص.

- [ ] enrichment از نام/شهر/دامنهٔ Lead استفاده کند و به lead_id مشخص attach شود؛ discovery مستقل کسب‌وکار جدید با آن مخلوط نشود.
- [ ] وب‌سایت official فقط با cross-evidence معتبر انتخاب شود؛ directory/aggregator برابر وب‌سایت رسمی نیست.
- [ ] snippet جای crawl وب‌سایت نیست؛ crawl مستقیم وب‌سایت در این فاز اضافه نمی‌شود.
- [ ] business email فقط اگر منبع بررسی‌شده عمومی حرفه‌ای باشد؛ email حدسی و ownership inference ممنوع.
- [ ] conflict به review؛ فیلدهای معتبر قبلی با حدس جدید overwrite نشوند.

**Tests:** `test_directory_not_promoted_to_official_site`, `test_unrelated_city_result_not_attached`, `test_enrichment_preserves_existing_contact`, `test_missing_evidence_stays_unverified`.
**Gate C:** mapping و allowlist source مستند؛ smoke پولی اختیاری با رضایت جدا؛ نتیجهٔ تست پولی شرط unit test نیست.

## 8. فاز D — تطبیق profile و بازبینی انسانی

### D1. evidence-based profile association

**Files:** ایجاد `src/enrichment/repository.py`؛ تغییر `src/enrichment/models.py`, `service.py`, `src/migrations.py`؛ تست `tests/test_profile_matching.py`.
**Produces:** ProfileCandidate با platform/url/status/reasons/confidence و review audit.

- [ ] status مستقل confirmed/probable/rejected؛ نام مشابه و follower count evidence هویت نیستند.
- [ ] confirmed: لینک به پروفایل از وب‌سایت رسمی قبلاً تأییدشده + evidence سازگار؛ بدون لینک مشاهده‌شده auto-confirm نشود.
- [ ] دامنه/تلفن/نشانی حرفه‌ای سازگار بدون لینک first-party: probable؛ conflict و نام‌تنها: unverified/rejected.
- [ ] اگر first-party linkage به crawl نیاز دارد، آن evidence در MVP دستی وارد شود؛ fetch مستقیم در scope نیست.
- [ ] human accept/reject با timestamp، actor identity یا local operator label و دلیل؛ رابطه «پروفایل کسب‌وکار» باشد نه «مالک».
- [ ] allowlist platform، HTTPS و canonical handle/channel ID؛ URL شخصی/محتوای غیرمرتبط کنار گذاشته شود.

**Tests:** `test_same_name_does_not_confirm_profile`, `test_first_party_link_with_consistent_evidence_confirms`, `test_conflicting_phone_requires_review`, `test_review_is_auditable`, `test_owner_not_inferred`.
**Gate D:** fixture حساب جعلی/هم‌نام/شعبه/حساب شخصی به confirmed نرسد.

## 9. فاز E — Connectorهای اجتماعی مستقل

هر adapter از `enrich(EnrichmentRequest) -> EnrichmentResult` استفاده می‌کند؛ `search(city, job)` به‌زور جایگزین profile URL input نمی‌شود. منابع disabled-by-default و اجرای batch تنها برای candidateهای confirmed یا probable انتخاب‌شده توسط کاربر مجاز است.

### E1. Instagram

**Files:** ایجاد `src/connectors/instagram.py` و `tests/test_instagram.py`، fixture `tests/fixtures/instagram/`؛ تغییر registry/config و integration docs.
- [ ] contract gate رسمی برای `apify~instagram-scraper`، profile mode و حذف posts/comments/followers extraction.
- [ ] allowlist: business profile URL، handle، public business bio/site و contact فقط با زمینه حرفه‌ای روشن؛ login/private content خارج از scope.
- [ ] not-found/private/blocked/partial از empty-success جدا شوند؛ هزینه و cap در source capability ثبت شوند.
**Tests:** `test_instagram_profile_mode_contract`, `test_private_profile_not_collected`, `test_posts_comments_not_retained`, `test_business_contact_requires_context`, `test_partial_dataset_safe`.

### E2. YouTube

**Files:** ایجاد `src/connectors/youtube.py`, `tests/test_youtube.py` و fixture `tests/fixtures/youtube/`؛ registry/config/docs.
- [ ] contract gate `streamers~youtube-scraper` برای channel input و channel identity؛ اگر Actor channel-only mode ندارد، mode کم‌دامنهٔ مجاز با هزینه مشخص تصویب شود یا منبع disabled بماند.
- [ ] allowlist channel URL/ID، نام و business description/official links؛ commenters و subscriber identities حذف.
- [ ] تعداد ویدئوها identity confidence ایجاد نکند؛ video data غیرلازم ذخیره نشود.
**Tests:** `test_youtube_channel_identity_contract`, `test_commenter_data_removed`, `test_video_only_result_not_fabricated_as_channel`, `test_channel_url_normalization`.

### E3. TikTok

**Files:** ایجاد `src/connectors/tiktok.py`, `tests/test_tiktok.py` و fixture `tests/fixtures/tiktok/`؛ registry/config/docs.
- [ ] contract gate `clockworks~tiktok-scraper` برای profile input؛ بدون جمع‌آوری audience/comment identities.
- [ ] allowlist URL/handle/business bio/official site؛ login/private/region restriction با error code امن.
- [ ] business association همان D؛ تعداد view و like، مالکیت یا confidence هویت را ثابت نکند.
**Tests:** `test_tiktok_profile_contract`, `test_personal_audience_data_removed`, `test_blocked_profile_not_success`, `test_popularity_not_identity_evidence`.

**Gate هر adapter:** mock request/status/dataset/pagination/redaction، privacy field checklist، docs و opt-in smoke. تأیید یکی مجوز فعال‌سازی بقیه نیست.

## 10. فاز F — orchestration چندمنبعی

### F1. pipeline با dependent steps و partial success

**Files:** ایجاد `src/pipeline.py`, `tests/test_pipeline.py`؛ تغییر execution service/worker، registry و CLI.
**Consumes:** B Job، C enrichment، D candidates، E adapters enabled.

- [ ] request sources allowlist؛ stages: places discovery → quality ingest → web enrichment → profile review/eligible selection → social enrichment.
- [ ] هر step، attempt، Run و budget جدا؛ یک Job correlation مشترک داشته باشد.
- [ ] source غیرفعال قبل از enqueue رد؛ social بدون candidate eligible حالت skipped با reason، نه اجرای بی‌هدف.
- [ ] شکست enrichment لید معتبر Places را حذف نکند؛ Job partial با خطای هر step؛ همهٔ steps ناموفق → failed.
- [ ] retry تنها steps failed امن؛ dependencyها بدون force دوباره اجرا نشوند.
- [ ] cached source به Campaign جدید membership بدهد، زمان گردآوری اصلی را حفظ کند؛ cascade هزینه بدون رضایت رخ ندهد.

**Tests:** `test_places_success_social_failure_is_partial`, `test_no_eligible_profile_skips_actor`, `test_retry_does_not_repeat_successful_paid_step`, `test_budget_stops_downstream_steps`, `test_same_business_multisource_one_identity`.
**Gate F:** scenario مصنوعی end-to-end برای city/job تا Lead enriched، membership و export؛ هیچ دادهٔ شخصی استنتاج نشود.

## 11. فاز G — Web UI پیشرفتهٔ محلی

### G1. job submit، progress و history

**Files:** ایجاد `src/web/job_routes.py`, `run_routes.py`, `templates/jobs.html`, `job_detail.html`, `runs.html`؛ تغییر app/routes/search/base/CSS؛ تست `tests/test_web_jobs.py`, `tests/test_web_runs.py`.

- [ ] POST search اعتبارسنجی و enqueue، سپس 303 به job detail؛ انتظار Actor داخل HTTP request حذف شود.
- [ ] polling هر 3 ثانیه فقط صفحهٔ فعال؛ terminal توقف؛ fallback بدون JS با refresh لینک. progress از steps واقعی.
- [ ] source انتخابی، سقف هزینه، estimate/actual/unknown، warnings، cancel_requested و needs_review واضح فارسی.
- [ ] GET job/status خواندنی؛ cancel/retry POST و CSRF-safe؛ provider messages خام نمایش داده نشوند.
- [ ] history با keyset pagination پیش‌فرض 50/max 100 و filter campaign/source/status/date؛ Query به service برود.
- [ ] Run comparison با observation snapshot همان زمان؛ مقایسهٔ payload فعلی Lead جای snapshot استفاده نشود.

**Tests:** `test_submit_redirects_without_waiting_for_actor`, `test_job_status_no_secret`, `test_retry_requires_post`, `test_pagination_filters`, `test_history_uses_original_observations`.

### G2. Lead detail، quality filters و review inbox

**Files:** ایجاد `src/web/lead_routes.py`, `templates/lead_detail.html`, `review.html`؛ تغییر campaign detail و CSS؛ تست `tests/test_web_quality.py`.

- [ ] جزئیات Lead ثابت، provenance هر field، freshness، اختلاف منبع و profile status جدا نمایش داده شوند.
- [ ] quality filters روی query و export مشترک؛ انتخاب campaign و فیلتر بدون divergence.
- [ ] accept/reject/merge با تأیید صریح، audit و server validation؛ GET هرگز mutation نکند.
- [ ] RTL، keyboard focus، label، error summary، mobile 360px، reduced-motion؛ لینک خارجی فقط http/https و خروجی escaped.
- [ ] در اولین deploy بدون اینترنت، وابستگی فونت external آشکار باشد؛ در صورت نیاز self-host فقط با بررسی مجوز.

**Tests:** `test_profile_probable_label`, `test_export_matches_visible_filters`, `test_review_mutation_requires_csrf`, `test_template_escapes_business_text`, `test_only_safe_external_urls`؛ visual/manual smoke با fixture ساختگی.
**Gate G:** کاربر بدون CLI campaign بسازد، job ارسال کند، status و error ببیند، review کند و export بگیرد؛ بدون Apify live در acceptance خودکار.

## 12. فاز H — دسترسی و انتشار اختیاری

### Decision Gate H0

فرض فعلی پلن: localhost تک‌کاربره باقی می‌ماند. قبل از H باید یکی از مسیرهای زیر تأیید شود:

1. ابزار شخصی محلی: H اختیاری و متوقف؛ CSRF/origin protection حتی بدون login حذف نمی‌شود.
2. تیم یک سازمان: roleهای admin/operator/viewer و داده مشترک؛ مناسب extension اولیه.
3. چندسازمانی: نیازمند طرح جدا برای tenant ownership و isolation، tenant-scoped unique keys/jobs/cache/export و ارزیابی PostgreSQL. **این مسیر با افزودن یک tenant_id ظاهری کامل نمی‌شود.**

### H1. team auth و authorization، فقط پس از انتخاب مسیر 2

**Files:** ایجاد `src/web/auth.py`, `src/auth/models.py`, `service.py`, `repository.py` و templates login؛ تغییر migrations/config/routes؛ tests `tests/test_auth.py`, `tests/test_web_permissions.py`.

- [ ] user/password hash با library نگهداری‌شدهٔ Argon2id پس از manifest change؛ بدون crypto دست‌ساز.
- [ ] session opaque server-side، expiry/rotation/logout/revocation؛ Secure در HTTPS، HttpOnly و SameSite؛ secret environment.
- [ ] admin مدیریت user/policy؛ operator ایجاد campaign/job/review؛ viewer read/export. تمام endpointهای job/Run/Lead/export مجوز بررسی کنند.
- [ ] CSRF token و trusted origin/host، login rate limit، audit؛ اطلاعات حساس و session در log نباشد.
- [ ] provisioning admin از command یک‌باره؛ بدون password پیش‌فرض و بدون ثبت password در command history.

**Tests:** `test_session_revocation`, `test_viewer_cannot_enqueue_or_review`, `test_export_requires_permission`, `test_csrf_and_origin_checks`, `test_login_rate_limit`, `test_no_default_credentials`.

### H2. controlled deployment

**Files:** deployment config مطابق مقصد تأییدشده، config/app و `docs/02-operations-guide.md`, `docs/08-troubleshooting.md`؛ tests `tests/test_deployment_settings.py`.

- [ ] HTTPS reverse proxy، trusted forwarded headers فقط برای proxy معلوم، secure cookies و host allowlist.
- [ ] worker مستقل تحت process manager، writable DB directory محدود، backup encrypted در صورت داشتن داده حساس و retention policy.
- [ ] health/readiness بدون secrets؛ account token server-side؛ bind عمومی فقط پس از security gate.
- [ ] SQLite فقط single-host و workload مناسب؛ lock contention پایدار، چند-host یا isolation پیچیده → gate PostgreSQL و migration plan مستقل.

**Gate H:** تست endpoint permission matrix، session/CSRF و threat review؛ backup/restore روی staging؛ هیچ exposure عمومی قبل از PASS.

## 13. فاز I — CRM، retention و سخت‌سازی

### I1. CRM-friendly export، نه اتصال خودکار

**Files:** ایجاد `src/crm_export.py`, `tests/test_crm_export.py`؛ تغییر CLI/web/export docs.
- [ ] canonical CRM schema v1: external_id=lead_id، business_name، business_phone، website، address، source_urls، collected_at، quality fields.
- [ ] generic CSV/JSON ابتدا؛ mapping vendor-specific فقط با CRM مقصد تأییدشده، نه فرض HubSpot/Salesforce.
- [ ] missing contact خالی، مالک نامعلوم خالی؛ duplicate/upsert key پایدار؛ escaped spreadsheet cells و timezone مستند.
- [ ] push API/OAuth/contact assignment خارج از این deliverable؛ قرارداد جدا در صورت درخواست.
**Tests:** `test_external_id_stable`, `test_no_guessed_owner_or_email`, `test_csv_formula_protection`, `test_crm_mapping_versioned`.

### I2. retention، observability و release gate

**Files:** execution/logging modules مرتبط، storage purge، docs operations/testing/history؛ tests `tests/test_retention.py`, `tests/test_operational_recovery.py`.
- [ ] retention raw اولیه 30 روز configurable؛ audit/provenance جدا و purge بدون شکستن evidence reference، با tombstone/metadata لازم.
- [ ] log structured: job_id/step_id/run_id/error_code/duration/count/cost-state؛ بدون payload/contact/token.
- [ ] metrics queue age، failures، partials، lease recovery، source latency، reservation outstanding و DB lock contention.
- [ ] backup سازگار WAL و restore rehearsal؛ startup schema check؛ هیچ downgrade اتوماتیک.
- [ ] CI آفلاین حداقل Python 3.10 و runtime جاری پروژه با dependency compatibility؛ Actor network و token لازم نباشد.
- [ ] fixture benchmark synthetic روی 10هزار Lead؛ زمان ingestion/query و peak memory اندازه‌گیری شوند؛ threshold از baseline اندازه‌گیری‌شده ثبت شود، عدد عملکرد حدسی ادعا نشود.

**Tests:** `test_purge_preserves_audit_metadata`, `test_backup_restore_preserves_jobs_and_memberships`, `test_logs_do_not_contain_credentials`, `test_worker_restart_keeps_budget_reservations`.
**Gate I:** suite/manifest health، recovery drill، compatibility matrix و release notes؛ باقی‌مانده‌ها آشکار ثبت شوند.

## 14. پذیرش end-to-end و failure matrix

| سناریو | انتظار |
|---|---|
| یک Places Lead در دو Campaign | یک lead_id، دو membership |
| تغییر تلفن کسب‌وکار | هویت ثابت با source ID، observation قدیم محفوظ |
| شعب مشترک با سایت یکسان | merge خودکار نشوند |
| دو حساب اجتماعی هم‌نام | confirmed نشوند |
| Google Search snippet درباره شخص | ownership/contact inference ذخیره نشود |
| worker بعد از دریافت provider ID قطع شود | poll/resume، نه start دوباره |
| remote start نتیجه نامعلوم | needs_review و reservation محفوظ |
| dataset pagination وسط راه fail | partial با count/evidence، نه success جعلی |
| budget کافی نیست | Actor بعدی start نشود |
| cancel هنگام Run فعال | ابتدا cancel_requested، terminal فقط با reconciliation |
| submit فرم دوبار | یک Job با idempotency key یکسان |
| cache hit | timestamp اصلی و source reuse آشکار |
| viewer درخواست mutation دهد | 403 و بدون side effect |
| export قدیمی بدون flags | fields و semantics پیشین حفظ |
| migration fail | DB قبلی سالم و schema version تغییر نکند |

## 15. سیاست تأیید، توقف و گزارش

- تصویب این master plan مجوز همهٔ اجرای پولی، انتشار عمومی یا جمع‌آوری جدید نیست.
- پس از تأیید کاربر، **ابتدا فقط A** اجرا شود و گزارش gate برای ادامه ارائه شود.
- هر gate شامل: deliverables، migration/backup impact، دستور و نتیجهٔ تست، هزینه/حریم خصوصی، محدودیت و پیشنهاد فاز بعدی.
- contract/pricing نامعلوم Actor، تضاد privacy، schema drift، data loss یا start_unknown unresolved باعث توقف همان step/source می‌شود؛ با حدس از آن عبور نشود.
- پروژهٔ multi-tenant، distributed queue، crawler وب مستقیم و CRM push نیاز به تصمیم و پلن مستقل دارند؛ scope creep محسوب می‌شوند.
- اسناد مستقیم به‌روزرسانی شوند: data model، architecture، integration، operations، testing، roadmap، handoff و history؛ skillهای مرتبط فقط در صورت تغییر workflow.
- CBM پس از تغییر architecture refresh شود؛ graph generated طبق `.gitignore` بماند و secrets index نشوند.

## 16. Self-review این پلن

- پوشش: Data Quality (A)، execution/budget/cache (B)، Google Search (C)، evidence/profile matching (D)، Instagram/YouTube/TikTok (E)، orchestration (F)، UI/history/progress (G)، auth/team/deployment (H)، CRM/retention/operations (I).
- سازگاری: CLI synchronous، export default، Campaign general و transaction semantics صریح حفظ شده‌اند.
- وابستگی: producer مدل/identity پیش از consumer؛ budget پیش از unattended pipeline؛ auth پیش از network exposure.
- خطرهای اصلی: mutable PK، shared branch identity، ambiguity remote start، confidence غیرکالیبره، ادعای سقف هزینهٔ provider و multi-tenant ناقص، با gate و تست مشخص پوشش داده شده‌اند.
- عدم توسعه: در تهیهٔ این سند فقط خواندن کد/مستندات و نوشتن همین پلن انجام شده؛ هیچ source، migration، dependency، Actor یا worker اجرا/تغییر داده نشده است.
