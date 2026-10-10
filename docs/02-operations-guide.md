# راهنمای عملیات

## اجرای معمول

1. محیط مجازی را فعال کنید.
2. وجود `APIFY_API_TOKEN` را بررسی کنید.
3. جست‌وجو را با `--limit` کنترل‌شده اجرا کنید.
4. خروجی را در `exports/` ذخیره کنید.
5. SQLite و خروجی‌ها را backup کنید.

## صف اجرای محلی

در فاز B، جدول `jobs` primitive صف محلی را فراهم می‌کند: ارسال تکراری با `idempotency_key` همان Job را برمی‌گرداند، Jobهای queued قابل claim توسط یک worker هستند و lease/fencing برای recovery اولیه ثبت می‌شود. handler مربوط به Places اکنون request را به `SearchLeadsService` متصل می‌کند؛ اگر request شامل `estimated_cost` و `max_cost` باشد، worker پیش از اجرا رزرو اتمیک می‌گیرد. Attemptهای provider شامل run/dataset، وضعیت و checkpoint در SQLite ثبت می‌شوند؛ runهای شناخته‌شده resume یا abort می‌شوند و پنجرهٔ نامشخص start به `needs_review` می‌رسد. Jobها هنوز باید با یک worker process مدیریت‌شده اجرا شوند؛ CI matrix پایتون نیز تا اجرای workflow در GitHub remote تأیید نهایی نمی‌شود.

## اجرای پنل وب محلی

```bash
uvicorn src.web.app:app --host 127.0.0.1 --port 8000
```

پنل در <http://127.0.0.1:8000> باز می‌شود. برای توقف سرور `Ctrl+C` بزنید. bind پیش‌فرض فقط localhost است؛ برای دسترسی شبکه‌ای یا اینترنتی این نسخه را تغییر ندهید.

## اجرای جداگانه

```bash
leadgen search "رستوران" "شیراز" --source places --db data/shiraz.db
leadgen export data/shiraz.json --format json --db data/shiraz.db
```

## مدیریت هزینه

- با limit کوچک شروع کنید.
- query دقیق بنویسید.
- شهرهای بزرگ را به منطقه تقسیم کنید.
- Actorهای شبکه‌های اجتماعی را در MVP فعال نکنید.
- runها را در Apify Console بررسی کنید.

## گزارش تست فاز ۲

در تاریخ ۲۰۲۶-۱۰-۰۷، فاز دوم با موفقیت اعتبارسنجی شد:

```text
pytest -q                 -> 4 passed
Places search limit=5    -> Saved 5 leads
JSON export              -> successful
CSV export               -> successful
SQLite database          -> test-phase2.db (48K)
```

فایل‌های آزمون در مسیر `exports/phase2/` تولید شدند. برای تست‌های بعدی از database جداگانه استفاده کنید تا `leads.db` اصلی تغییر نکند.

## مدیریت secret

در صورت افشای token، فوراً آن را در Apify revoke و token جدید ایجاد کنید. `.env` نباید commit شود.

## Production hardening

- `GET /health/live` is a content-free liveness check.
- `GET /health/ready` verifies that the existing SQLite file and required schema tables are readable; it never creates an empty database. It returns `503` with a stable database/schema code when readiness fails. The local web app reports `worker: "not_required"` because CLI workers are separate processes.
- CLI workers renew their SQLite lease through a separate heartbeat connection during long-running handlers; losing the fencing lease prevents stale result persistence.
- The worker recovers expired leases before claiming new work. Fencing tokens prevent stale workers from updating reclaimed jobs.
- `JobWorker.stop()` provides cooperative shutdown and prevents new claims after the stop signal.
- Jobs in `needs_review` are listed with their persisted provider attempts at `GET /api/jobs/{job_id}`. Resolve them with `POST /api/jobs/{job_id}/resolve`: `attach_run` links a run found in the provider console and resumes it; `retry` requires `confirmed_no_remote_run: true` after checking Apify; `abandon` marks the job cancelled. Never choose retry unless the provider console confirms no run was created.
