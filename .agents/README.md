# Project Agent Playbook

این پوشه دستورالعمل‌های مخصوص ایجنت‌های هوش مصنوعی پروژه است. قبل از هر تغییر، [../docs/README.md](../docs/README.md) و این فایل را بخوانید.

## ترتیب استفاده

1. `apify-integration`: هر کار مرتبط با Actor، run، dataset یا token
2. `lead-extraction`: طراحی query و استخراج لید
3. `data-quality`: normalization، deduplication و scoring
4. `privacy-compliance`: بررسی داده عمومی، حریم خصوصی و مالکیت
5. `python-testing`: افزودن تست و اعتبارسنجی تغییرات

## قوانین غیرقابل مذاکره

- secret را در خروجی، log، commit یا گزارش چاپ نکن.
- `APIFY_API_TOKEN` تنها credential فعلی برای Places است؛ Google API key استفاده نمی‌شود.
- قبل از تغییر قرارداد داده، تست و مستندات را به‌روزرسانی کن.
- فقط داده عمومی و حرفه‌ای کسب‌وکار را پردازش کن.
- برای هر تغییر، تست‌های مرتبط را اجرا و نتیجه را گزارش کن.

## مهارت‌های استفاده‌شده در توسعه پروژه

این فهرست برای ثبت سابقه تصمیم‌های مهندسی و انتخاب skillها نگهداری می‌شود:

| Skill | کاربرد در این پروژه |
|---|---|
| `project-apify-integration` | طراحی و ممیزی Actor، dataset، احراز هویت، retry و تست mock شده Apify |
| `project-data-quality` | normalization، scoring، provenance و deduplication لیدها |
| `project-privacy-compliance` | محدودسازی داده به اطلاعات عمومی و حرفه‌ای و جلوگیری از استنتاج مالکیت/person data |
| `project-lead-extraction` | تعریف query/location، محدودیت source و قرارداد استخراج لید |
| `project-python-testing` | TDD، تست‌های regression، تست آفلاین و معیار پذیرش Python |
| `brainstorming` | انتخاب رویکرد اصلاح مرحله‌ای و تأیید طراحی معماری پیش از اجرا |
| `writing-plans` | تبدیل طراحی تأییدشده به برنامه اجرایی وابستگی‌دار و قابل‌تست |
| `documentation-writer` | ثبت تغییرات، معماری، عملیات و وضعیت نهایی در مستندات Diátaxis-oriented |
| `git-commit` | ایجاد commitهای Conventional Commit و جلوگیری از ورود secretها به تاریخچه |

جزئیات تغییرات و نتایج اعتبارسنجی در [تاریخچه تغییرات](../docs/11-change-history.md) ثبت شده است.
