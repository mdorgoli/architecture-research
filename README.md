# مدیریت هزینه‌ها با FastAPI، SQLAlchemy و Alembic

نسخهٔ دیتابیسی تمرین هزینه‌ها با SQLite، مدل ورودی/خروجی Pydantic و نمودار drawio در پوشهٔ docs.

## نصب و اجرا در Windows

Python 3.10 یا جدیدتر لازم است. از ریشهٔ پروژه اجرا کنید:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn main:app --reload
```

مستندات تعاملی: http://127.0.0.1:8000/docs

دیتابیس پیش‌فرض `expenses.db` کنار کد است. داده‌ها با restart باقی می‌مانند. برای فایل دیگر، پیش از اجرای Alembic و API در همان ترمینال تنظیم کنید:

```powershell
$env:DATABASE_URL = "sqlite:///./my-expenses.db"
```

این تنظیم برای این تمرین با SQLite آزمایش شده است.

## API

| متد | مسیر | پاسخ موفق |
|---|---|---|
| POST | /expenses | 201 |
| GET | /expenses | 200 |
| GET | /expenses/{expense_id} | 200 |
| PUT | /expenses/{expense_id} | 200 |
| DELETE | /expenses/{expense_id} | 204 بدون بدنه |

بدنهٔ POST و PUT:

```json
{"description": "خرید کتاب", "amount": 150000.5}
```

شناسه را سرور می‌سازد. توضیح غیرخالی و مبلغ مثبت و متناهی الزامی است؛ رشتهٔ عددی، بولی و فیلد اضافی رد می‌شوند. هزینهٔ ناموجود پاسخ 404 و ورودی نامعتبر پاسخ 422 دارد. پاسخ‌های دارای بدنه با `ExpenseOutput` بررسی می‌شوند.

## فایل‌ها و طراحی

- `database.py`: Engine، Base و Session مختص هر درخواست.
- `models.py`: مدل ORM و قیدهای جدول expenses.
- `schemas.py`: مدل‌های Pydantic ورودی و خروجی.
- `alembic.ini` و `alembic/`: تنظیمات، قالب و migration اولیه.
- [نمودار قابل ویرایش drawio](docs/expense-database.drawio): با Open Existing Diagram در diagrams.net باز کنید.
- [شرح طراحی](docs/database-design.md): جدول‌ها، نوع فیلدها، اتصال و محدودیت‌ها.

## مدیریت migration

```powershell
.venv\Scripts\python -m alembic current
.venv\Scripts\python -m alembic check
# پس از تغییر مدل، migration پیشنهادی را بسازید و کد آن را بازبینی کنید:
.venv\Scripts\python -m alembic revision --autogenerate -m "describe change"
.venv\Scripts\python -m alembic upgrade head
```

بازگشت به base جدول هزینه‌ها و داده‌های آن را حذف می‌کند؛ فقط برای دیتابیس آزمایشی:

```powershell
.venv\Scripts\python -m alembic downgrade base
```

## تست

```powershell
.venv\Scripts\python -m pip install -r requirements-test.txt
.venv\Scripts\python -m unittest -v
```

تست‌ها روی فایل SQLite موقت و مستقل اجرا می‌شوند. CRUD، اعتبارسنجی، ماندگاری، قید SQL، ارتقا و بازگشت migration و تطابق مدل با schema بررسی می‌شوند.

این پروژه آموزشی تک‌کاربره است؛ احراز هویت و پرداخت در محدودهٔ تمرین نیستند. مبلغ float مطابق تمرین قبلی حفظ شده است.

تحقیق قبلی معماری در شاخهٔ [docs/monolithic-microservices-fa](https://github.com/mdorgoli/architecture-research/tree/docs/monolithic-microservices-fa) و فایل‌های قبلی docs محفوظ است.
