# حساب‌روز — مدیریت هزینه شخصی

برنامهٔ فارسی و راست‌به‌چپ با Django، PostgreSQL، Gunicorn و WhiteNoise. ثبت‌نام و ورود، ثبت/ویرایش/حذف هزینه، دسته‌بندی اختصاصی، فیلتر ماه و دسته، جمع هزینه و نمودار سهم دسته‌ها دارد. تاریخ‌ها **میلادی** و مبالغ **تومان بدون اعشار** هستند. این برنامه دفتر ثبت هزینه است؛ درگاه پرداخت، اتصال بانکی یا حسابداری رسمی ندارد.

شاخهٔ تمرین: `feat/expense-manager-production`؛ پوشهٔ برنامه: `expense-manager`؛ Dockerfile و Compose در ریشهٔ مخزن هستند. تحقیق قبلی در `docs` حفظ شده است.

## اجرای پیشنهادی با Docker و PostgreSQL

در ریشهٔ مخزن:

```sh
cp .env.example .env
# LOCAL_DB_PASSWORD را در .env به یک مقدار تصادفی تغییر دهید.
docker compose up -d --build
```

در PowerShell به‌جای دستور اول: `Copy-Item .env.example .env`.
سایت: http://127.0.0.1:8000 — حساب خود را بسازید؛ هیچ حساب یا رمز پیش‌فرضی وجود ندارد.

Compose برای توسعهٔ محلی است: اتصال وب HTTP و اتصال PostgreSQL در شبکهٔ خصوصی Docker بدون TLS است؛ پورت دیتابیس عمومی نیست. برای production از تنظیمات جداگانهٔ راهنمای همروش استفاده کنید.

```sh
docker compose exec web python manage.py test expenses --noinput
docker compose exec web python manage.py createsuperuser
docker compose logs --tail 100 web
docker compose down
```

`down` داده‌ها را در volume نگه می‌دارد. `down -v` داده‌ها را پاک می‌کند؛ برای استفادهٔ عادی اجرا نکنید. در به‌روزرسانی، پیش از راه‌اندازی نسخهٔ جدید، migration را با `docker compose run --rm release` اجرا کنید.

## توسعه بدون Docker

Python 3.14 لازم است. در پوشهٔ `expense-manager`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:APP_ENV='development'
$env:DJANGO_DEBUG='1'
python manage.py migrate
python manage.py runserver
```

این حالت از SQLite استفاده می‌کند. برای Bash: `export APP_ENV=development DJANGO_DEBUG=1` و فعال‌سازی با `source .venv/bin/activate`.
فایل‌های `.env` خودکار توسط Django خوانده نمی‌شوند؛ Compose آن‌ها را برای جای‌گذاری متغیرها می‌خواند. روی سرور متغیرها را از پنل وارد کنید.

## بررسی کیفیت

```sh
python -m black --check .
python -m flake8 .
python manage.py collectstatic --noinput
python manage.py makemigrations --check --dry-run
python manage.py test expenses --noinput
```

تست‌ها مالکیت داده، دست‌کاری شناسه و دستهٔ کاربر دیگر، CSRF، اعتبار مبلغ و تاریخ، ثبت‌نام/ورود، قفل ورود، فیلتر و جمع گزارش، خروج امن، escape متن کاربر، سلامت دیتابیس و حذف دادهٔ حساس از Sentry را پوشش می‌دهند. در production نیز `python manage.py check --deploy --fail-level WARNING` اجرا شود. workflow گیت‌هاب تست‌ها را با PostgreSQL و سپس ساخت ایمیج اجرا می‌کند.

## ساختار

- `config/settings.py`: پیکربندی محیطی، امنیت، دیتابیس و Sentry
- `expenses/`: مدل‌ها، فرم‌ها، کنترل دسترسی، migration و تست‌ها
- `templates/` و `static/`: رابط فارسی؛ بدون CDN و وابستگی بیرونی مرورگر
- `entrypoint.sh`: انتظار محدود برای دیتابیس، migration مجزا، جمع‌آوری static و اجرای Gunicorn
- `DEPLOY-HAMRAVESH.md`: راهنمای استقرار، SSL، Sentry، بکاپ و بازگشت نسخه
- `VERIFICATION.md`: نتیجهٔ بررسی‌های انجام‌شده و مرز موارد تأییدنشده

## ملاحظات امنیتی

در تمام مسیرهای برنامه، داده بر اساس کاربر جاری فیلتر می‌شود و owner از POST پذیرفته نمی‌شود. مدیر دارای مجوز مدیریت کاربران در `/admin/` یک نقش مورداعتماد است. هزینه‌ها در admin ثبت نشده‌اند. کنترل مالکیت دسته در مدل نیز اجرا می‌شود؛ نوشتن مستقیم SQL یا `QuerySet.update` از این اعتبارسنجی عبور می‌کند و نباید به مسیرهای ورودی کاربر اضافه شود.

فرم‌ها CSRF دارند؛ عملیات حذف و خروج فقط POST هستند. رمز حداقل ۱۲ نویسه و با هش استاندارد Django نگه‌داری می‌شود. Axes بعد از ۵ تلاش ناموفق، نام کاربری و IP اتصال را ۱۵ دقیقه محدود می‌کند. **پشت پراکسی، IP اتصال ممکن است بین کاربران مشترک باشد**؛ قبل از استفادهٔ عمومی، دریافت IP واقعی فقط از پراکسی مورداعتماد و محدودسازی نرخ ثبت‌نام در لبهٔ شبکه را با زیرساخت تنظیم کنید. هیچ هدر IP دلخواهی در برنامه قابل‌اعتماد فرض نشده است.

رمز، کلید Django و DSN را وارد Git نکنید. production بدون کلید قوی، host صریح، origin HTTPS و PostgreSQL آغاز نمی‌شود. Sentry تا وقتی DSN تنظیم نشود خاموش است؛ متن خطا، بدنهٔ درخواست، اطلاعات کاربر، breadcrumb و متغیرهای محلی از رخداد ارسالی حذف می‌شوند. این محدودیت عامدانه است تا اطلاعات هزینه‌ها وارد ابزار مانیتورینگ نشوند. بازیابی رمز از طریق ایمیل و تأیید ایمیل در این نسخه وجود ندارد.
