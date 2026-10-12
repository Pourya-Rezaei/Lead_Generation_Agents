# تست و کیفیت

## Current release boundary (2026-10-11)

Only Google Places and independent Instagram Search are executable. Instagram is standard-only (`liveSearch=false`, enhancement=false), one comma-free phrase, default 10 and limit 1..250. Requests, profiles, reload and exports are source-specific; no contact extraction or geographic guarantee. Existing SQLite/history are preserved. Any references below to Google Search, LinkedIn, YouTube, TikTok or Instagram enrichment are **historical**, not active product capabilities. See [the current integration contract](06-apify-integration.md) and [operations](02-operations-guide.md). No paid smoke or live-mode certification was performed.


## اجرای تست

```bash
source .venv/bin/activate
pytest -q
```

## انواع تست فعلی

- Connector با HTTP mock شده
- mapping و normalization
- scoring
- SQLite round-trip
- export JSON/CSV

## قانون تست تغییرات

هر تغییر در schema، connector یا storage باید حداقل یک تست regression داشته باشد. تست‌ها نباید token واقعی یا شبکه واقعی مصرف کنند.

## نتیجه آخرین اعتبارسنجی

آخرین اجرای کامل محلی روی Python 3.10 تا 3.14 موفق بود:

```text
Python 3.10: 197 passed, 1 warning
Python 3.11: 197 passed, 1 warning
Python 3.12: 197 passed, 1 warning
Python 3.13: 197 passed, 1 warning
Python 3.14: 197 passed, 1 warning
```

هشدار باقی‌مانده، deprecation از Starlette برای استفادهٔ TestClient/httpx است. اجرای remote در GitHub Actions هنوز نیازمند اتصال repository به remote است. هیچ Actor پولی در این اعتبارسنجی اجرا نشده است.
