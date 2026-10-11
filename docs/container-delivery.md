# ساخت و تحویل خودکار کانتینر

گزارش مقایسهٔ تک‌مرحله‌ای و چندمرحله‌ای: [Word](docker-cicd-report-fa.docx) و [متن قابل مشاهده در GitHub](docker-cicd-report-fa.md).

## ساخت و آزمون محلی

```powershell
docker build --target runtime -t expense-api:local .
python scripts/container_smoke.py expense-api:local
```

Docker Engine باید فعال باشد. اسکریپت یک کلید تصادفی موقت می‌سازد، کانتینر با دیتابیس موقت و پورت loopback تصادفی اجرا می‌کند و پس از آزمون آن را حذف می‌کند. هیچ کلید یا دادهٔ واقعی برای این آزمون لازم نیست. image ساخته‌شده باقی می‌ماند.

مراحل Dockerfile: dependencies برای محیط مجازی، translations برای کامپایل PO/MO و runtime برای اجرا. image پایه با digest و نسخهٔ وابستگی‌های مستقیم ثابت شده؛ وابستگی‌های انتقالی هنوز lock کامل ندارند. به‌روزرسانی پایه و بسته‌ها باید با بازاجرای تست‌ها انجام شود.

## اجرای ماندگار با Compose

```powershell
$env:JWT_SECRET = (& python -c "import secrets; print(secrets.token_hex(32))")
$env:APP_ORIGIN = "https://localhost:8443"
docker compose build
docker compose run --rm api python -m alembic upgrade head
docker compose run --rm api python create_user.py student
docker compose up -d
docker compose ps
```

کلید را برای اجراهای بعدی ثابت و امن نگه دارید. Compose آن را از محیط دریافت می‌کند؛ secret داخل image نیست. volume نام‌دار expense-data فایل SQLite را در /data نگه می‌دارد. `docker compose down` کانتینر را متوقف می‌کند؛ `down -v` دادهٔ volume را حذف می‌کند و برای استفادهٔ عادی مناسب نیست.

Compose فقط پورت 8000 را روی 127.0.0.1 میزبان باز می‌کند. یک reverse proxy با گواهی معتبر باید HTTPS مبدأ APP_ORIGIN را به این پورت متصل کند. HTTP برای healthcheck داخلی است؛ کوکی‌های Secure همچنان برای مرورگر به HTTPS نیاز دارند. این پروژه گواهی یا سرور عمومی ایجاد نمی‌کند. مهاجرت دیتابیس به‌صورت دستور جدا انجام می‌شود و نباید هم‌زمان توسط چند replica اجرا شود.

## Workflow

فایل `.github/workflows/ci-cd.yml` سه job وابسته دارد:

1. **test:** نصب Python 3.12، کامپایل ترجمه و بررسی نبود اختلاف با MO ثبت‌شده، اجرای unittest.
2. **build:** ساخت runtime، اجرای smoke روی کانتینر واقعی و ذخیرهٔ همان image به artifact سه‌روزه.
3. **publish:** بارگیری artifact و ارسال همان image به GHCR با tag `sha-<commit>`.

push به main یا feat/docker-cicd و tagهای v باعث اجرا می‌شود. pull request فقط تست و ساخت می‌کند و مجوز انتشار ندارد. workflow_dispatch نیز تعریف شده؛ دکمهٔ اجرای دستی معمولاً پس از قرارگرفتن workflow در شاخهٔ پیش‌فرض در دسترس است. اکشن‌های رسمی با SHA مشخص شده‌اند و فقط job انتشار packages:write دارد. هیچ secret بلندمدت GHCR لازم نیست؛ GITHUB_TOKEN همان اجرای Actions استفاده می‌شود. اگر تنظیمات سازمان یا repository انتشار package را منع کنند، publish باید در Actions بررسی شود.

نام image:

```text
ghcr.io/mdorgoli/architecture-research/expense-api:sha-<full-commit-sha>
```

عمومی‌بودن repository به‌معنی عمومی‌بودن خودکار package نیست. GHCR ممکن است برای pull به احراز هویت نیاز داشته باشد؛ سطح دسترسی package باید جدا بررسی شود. tag مبتنی بر commit انتخاب نسخه را واضح می‌کند؛ برای استقرار سخت‌گیرانه digest خود image را ثبت و استفاده کنید.

## مرز CD و استقرار

این تمرین Continuous Delivery تا registry را انجام می‌دهد. مقصد سرور تعیین نشده، پس deploy به production در workflow نیست. برای استقرار بعدی لازم است میزبان و مسیر HTTPS تعیین شود، secrets در محیط اجرا قرار گیرند، از دیتابیس پشتیبان تهیه شود و image منتخب و migration آن با healthcheck بررسی شوند. برای rollback، سازگاری schema با image قبلی مهم است و صرف تغییر tag کافی نیست.

آزمون smoke فقط آمادگی کانتینر، migration، ترجمه و محدودیت‌های اجرایی را بررسی می‌کند؛ تست‌های احراز هویت و CSRF در job test اجرا می‌شوند. این زنجیره جایگزین اسکن آسیب‌پذیری، بازبینی امنیتی یا آزمون بار نیست.
