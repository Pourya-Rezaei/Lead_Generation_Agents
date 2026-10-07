# Project Agent Playbook

این پوشه دستورالعمل‌های مخصوص ایجنت‌های هوش مصنوعی پروژه است. قبل از هر تغییر، [../doc/README.md](../doc/README.md) و این فایل را بخوانید.

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
