# طراحی اجرای Graphify و یکپارچه‌سازی Agent

## هدف

Graphify به‌عنوان ابزار کمکی برای شناخت معماری پروژه و ساخت graph محلی استفاده شود، بدون وابستگی به سرویس خارجی، بدون ورود secret یا داده واقعی، و بدون تحمیل مجموعه‌ای از دستورات طولانی به هر Agent.

## محدوده

1. نصب Graphify در محیطی جدا از محیط `.venv` پروژه.
2. اجرای استخراج ساختاری روی کد و مستندات انتخاب‌شده.
3. تولید artifactهای محلی شامل graph JSON، گزارش و visualization در مسیر اختصاصی.
4. ساخت یک wrapper کوتاه با فرمان‌های ثابت برای build، status و queryهای پایه.
5. ثبت دستورالعمل استفاده برای Agentها و به‌روزرسانی مستندات مرتبط.
6. خارج نگه‌داشتن artifactها، cacheها و dependencyهای ابزار از Git.

## رویکرد معماری

Graphify ابزار اصلی persistence یا application runtime نیست. artifactهای آن صرفاً برای codebase intelligence هستند و خارج از مسیر اجرای Lead Generation قرار می‌گیرند.

Wrapper مسئول انتخاب مسیر Graphify، تعیین root پروژه، حذف مسیرهای حساس از corpus، ایجاد output directory و گزارش خطاهای قابل‌فهم است. اجرای آن باید local و deterministic باشد؛ semantic extraction وابسته به LLM در این فاز فعال نمی‌شود.

## ورودی و خروجی

ورودی پیش‌فرض، فایل‌های source و documentation پروژه است. این مسیرها نباید index شوند: `.env*` به‌جز `.env.example`، دیتابیس‌ها، `exports/`، محیط مجازی، cacheها، `.git/` و artifactهای قبلی Graphify.

خروجی‌ها در یک directory محلی ignored قرار می‌گیرند و شامل `graph.json` و گزارش/visualization تولیدشده هستند. هیچ token، raw lead یا payload واقعی نباید در خروجی قرار گیرد.

## رابط Agent

Agent به‌جای دانستن مسیرهای Python و dependencyها از wrapper استفاده می‌کند:

```text
./tools/graphify build
./tools/graphify status
./tools/graphify query "SearchResult"
./tools/graphify impact "SearchResult"
```

اگر Graphify نصب نباشد یا artifact وجود نداشته باشد، wrapper باید پیام راهنمای روشن بدهد و موفقیت جعلی گزارش نکند.

## محدودیت‌ها

Graphify در این پروژه به‌عنوان ابزار visualization و architecture exploration استفاده می‌شود، نه جایگزین تست، type checking، خواندن کد یا تحلیل قطعی blast radius. روابط dynamic و semantic inference باید با برچسب عدم‌قطعیت گزارش شوند.

## اعتبارسنجی

- اجرای build روی پروژه بدون درخواست شبکه‌ای به Apify.
- بررسی نبود secret و فایل حساس در corpus و output.
- اجرای status و حداقل یک query واقعی.
- اجرای `pytest -q` پس از تغییرات.
- بررسی `git status` و اطمینان از ignored بودن محیط و artifactهای Graphify.
