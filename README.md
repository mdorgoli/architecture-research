# مدیریت هزینه‌ها با احراز هویت JWT و چند زبان

FastAPI + Pydantic + SQLAlchemy + SQLite + Alembic. نسخهٔ این شاخه ورود، خروج، تمدید نشست و مالکیت هزینه‌ها را به تمرین قبلی اضافه می‌کند.

## راه‌اندازی

Python 3.10+ لازم است. در ریشهٔ پروژه و PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
$env:JWT_SECRET = (& .venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))")
$env:APP_ORIGIN = "https://localhost:8443"
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python create_user.py student
```

رمز کاربر به‌صورت مخفی پرسیده می‌شود؛ حداقل ۱۲ و حداکثر ۱۲۸ کاراکتر. کاربر یا رمز پیش‌فرض وجود ندارد. نام کاربری ۳ تا ۶۴ کاراکتر از حروف و اعداد لاتین و `_.-` است. ثبت‌نام عمومی در محدودهٔ تمرین نیست.

کلید JWT را یک بار تصادفی بسازید و برای اجراهای بعدی در محیط امن نگه دارید؛ دستور بالا در هر اجرا کلید تازه می‌سازد و توکن‌های قبلی را نامعتبر می‌کند. برنامه بدون کلید حداقل ۳۲ بایتی شروع نمی‌شود. کلید یا رمز را داخل Git نگذارید. فایل `.env` خودکار بارگذاری نمی‌شود.

## HTTPS محلی

کوکی‌ها همیشه Secure هستند؛ آن‌ها را برای اجرای HTTP ضعیف نکنید. پس از نصب [mkcert](https://github.com/FiloSottile/mkcert)، برای توسعهٔ محلی:

```powershell
mkcert -install
mkcert -key-file localhost-key.pem -cert-file localhost.pem localhost 127.0.0.1 ::1
.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8443 --ssl-keyfile localhost-key.pem --ssl-certfile localhost.pem
```

`mkcert -install` مرجع گواهی توسعه را به سیستم مورد اعتماد اضافه می‌کند؛ کلید خصوصی آن را به اشتراک نگذارید. این تنظیم برای توسعه است. در استقرار واقعی HTTPS و تنظیم پروکسی مورد اعتماد لازم است.

مستندات API: https://localhost:8443/docs

دیتابیس پیش‌فرض فایل `expenses.db` کنار کد است. برای مسیر دیگر، پیش از اجرای Alembic و API متغیر `DATABASE_URL` را تنظیم کنید؛ مثال: `sqlite:///./my-expenses.db`.

## مسیرها

| متد | مسیر | نتیجه |
|---|---|---|
| GET | /auth/csrf | دریافت توکن CSRF پیش از ورود؛ 200 |
| POST | /auth/login | اعتبارسنجی رمز و تنظیم کوکی‌ها؛ 200 |
| POST | /auth/refresh | تعویض توکن‌ها بدون رمز؛ 200 |
| POST | /auth/logout | ابطال نشست و پاک‌کردن کوکی‌ها؛ 204 |
| GET | /auth/me | شناسه و نام کاربر جاری؛ 200 |
| POST | /expenses | ایجاد هزینه برای کاربر جاری؛ 201 |
| GET | /expenses | فقط هزینه‌های کاربر جاری؛ 200 |
| GET / PUT / DELETE | /expenses/{expense_id} | خواندن / ویرایش / حذف؛ 200 / 200 / 204 |

بدنهٔ ورود `{"username":"student","password":"رمز انتخابی شما"}` است. بدنهٔ ایجاد/ویرایش هزینه مانند قبل `{"description":"خرید کتاب","amount":150000.5}` است. هزینهٔ ناموجود یا متعلق به دیگری 404، ورودی نامعتبر 422، مشکل احراز هویت 401 و شکست CSRF برابر 403 است.

هر درخواست تغییردهنده، حتی ورود، به Origin برابر APP_ORIGIN و هدر `X-CSRF-Token` برابر کوکی `__Host-csrf` نیاز دارد. مرورگر Origin را خودش می‌فرستد. پس از ورود، مقدار CSRF جدید را از پاسخ ورود یا کوکی بخوانید. Swagger به‌تنهایی هدر CSRF را اضافه نمی‌کند؛ برای آزمایش کامل از نمونه‌کلاینت زیر یا کلاینتی با cookie jar استفاده کنید.

## نمونهٔ قابل اجرا و تمدید خودکار

```powershell
.venv\Scripts\python -m pip install -r requirements-test.txt
$env:SSL_CERT_FILE = Join-Path (mkcert -CAROOT) "rootCA.pem"
.venv\Scripts\python examples/session_client.py student
```

نمونهٔ `SessionClient` در صورت پایان اعتبار یا حذف کوکی Access، یک بار refresh انجام می‌دهد و درخواست را تکرار می‌کند؛ رمز فقط هنگام ورود لازم است. خطای refresh به فراخواننده برمی‌گردد تا ورود دوباره انجام شود. نمونهٔ ترتیبی است؛ کلاینت چنددرخواستی باید refreshها را هماهنگ کند تا هم‌زمان یک refresh ارسال شود.

## تست و migration

```powershell
.venv\Scripts\python -m unittest -v
.venv\Scripts\python -m alembic current
.venv\Scripts\python -m alembic check
```

تست‌ها دیتابیس موقت و کلید تصادفی خودشان را می‌سازند و به گواهی محلی احتیاج ندارند. `0002` کاربران، نشست‌ها و مالکیت هزینه را اضافه می‌کند. هزینه‌های قدیمی حفظ می‌شوند ولی چون مالکشان معلوم نیست در API نمایش داده نمی‌شوند. نسبت‌دادن آن‌ها نیاز به بررسی دستی مالک دارد.

`alembic downgrade 0001` اطلاعات کاربران، نشست‌ها و مالکیت را حذف می‌کند و فقط برای آزمایش مناسب است؛ `downgrade base` هزینه‌ها را هم حذف می‌کند. قبل از migration دادهٔ واقعی نسخهٔ پشتیبان بگیرید.

## مستندات

- [طراحی و نکات امنیتی JWT، کوکی، XSS و CSRF](docs/authentication.md)
- [Schema نسخهٔ جدید](docs/database-design.md)
- [نمودار drawio احراز هویت و روابط](docs/auth-schema.drawio)
- نسخهٔ دیتابیس قبلی: شاخهٔ `feat/expense-database`؛ تحقیق معماری: شاخهٔ `docs/monolithic-microservices-fa`.

این تمرین آموزشی است. محدودسازی تلاش ورود، MFA، بازیابی رمز و عملیات حساب کاربری در آن پیاده‌سازی نشده‌اند؛ استفادهٔ عمومی به تکمیل این بخش‌ها و بازبینی استقرار نیاز دارد.

## چندزبانی

فارسی و انگلیسی با PO/MO پشتیبانی می‌شوند. نمونه: `GET /welcome?lang=fa` یا هدر `Accept-Language: fa-IR`. پارامتر lang اولویت دارد و زبان پیش‌فرض انگلیسی است.

`/about` و `/expenses/summary` نیز پیام ترجمه‌شده دارند؛ مسیر خلاصه به ورود نیاز دارد. پیام‌های ورود، تمدید نشست و خطاها ترجمه می‌شوند؛ کدهای ماشینی و دادهٔ کاربر ثابت‌اند.

[راهنمای انتخاب زبان، فایل‌ها، افزودن زبان و چالش‌ها](docs/internationalization.md)

برای تغییر ترجمه‌ها، requirements-i18n.txt را نصب و scripts/compile_translations.py را اجرا کنید. فایل‌های MO آماده در مخزن هستند. این شاخه `feat/multilingual-api` است و نسخهٔ قبلی احراز هویت در `feat/jwt-auth` محفوظ است.

## Docker و CI/CD

Dockerfile چندمرحله‌ای، .dockerignore، compose.yaml و workflow در `.github/workflows/ci-cd.yml` اضافه شده‌اند. مراحل خودکار: تست‌ها ← ساخت و smoke test کانتینر ← انتشار همان image در GHCR.

- [راهنمای ساخت، اجرا، migration و تحویل image](docs/container-delivery.md)
- [گزارش فارسی Word: تک‌مرحله‌ای و چندمرحله‌ای](docs/docker-cicd-report-fa.docx)
- [نسخهٔ متنی گزارش](docs/docker-cicd-report-fa.md)

شاخهٔ این تمرین `feat/docker-cicd` است. workflow استقرار روی سرور عمومی ندارد، زیرا مقصد استقرار تعیین نشده است.
