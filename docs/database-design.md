# طراحی دیتابیس مدیریت هزینه‌ها

فایل قابل ویرایش در diagrams.net / draw.io: `expense-database.drawio`.

## محدوده و فرض‌ها

این تمرین تک‌کاربره است و همان سه فیلد تمرین قبل را نگه می‌دارد. جدول کاربر، دسته‌بندی و رابطهٔ خارجی اضافه نشده، چون در نیازمندی وجود ندارند. یک جدول مستقل برای این محدوده کافی است.

| ستون | نوع SQLAlchemy / SQLite | قید |
|---|---|---|
| id | Integer / INTEGER | کلید اصلی؛ AUTOINCREMENT |
| description | Text / TEXT | NOT NULL؛ پس از trim غیرخالی |
| amount | Float / FLOAT | NOT NULL؛ مثبت و متناهی |

SQLite جدول داخلی `sqlite_sequence` را برای شمارنده می‌سازد. Alembic نیز جدول `alembic_version` را برای نسخهٔ schema مدیریت می‌کند؛ این جدول با expenses رابطهٔ خارجی ندارد.

## اتصال و چرخهٔ درخواست

FastAPI ← اعتبارسنجی Pydantic → Session مختص درخواست → مدل Expense → Engine → فایل SQLite.
در ایجاد، ویرایش و حذف، تغییرات commit می‌شوند. Session در پایان درخواست بسته می‌شود؛ تراکنش commitنشده هنگام بسته‌شدن برگشت می‌خورد. شناسهٔ حذف‌شده در SQLite دوباره تخصیص نمی‌یابد.

`database.py` آدرس را از متغیر محیطی `DATABASE_URL` می‌خواند. مقدار پیش‌فرض فایل `expenses.db` کنار کد پروژه است؛ API و Alembic از یک تنظیم مشترک استفاده می‌کنند. فایل دیتابیس و اطلاعات محیطی وارد Git نمی‌شوند.

## Schema و migration

`models.py` ساختار ORM، `schemas.py` قرارداد ورودی/خروجی و migration شمارهٔ `0001` ایجاد جدول را تعریف می‌کنند. جدول‌ها فقط با Alembic ساخته می‌شوند؛ هنگام اجرای API از `create_all` استفاده نمی‌شود. دستور downgrade جدول و داده‌های آن را حذف می‌کند و فقط باید روی دیتابیس آزمایشی اجرا شود.

اعتبارسنجی API از قید SQL دقیق‌تر است: فاصله‌های ابتدا و انتهای توضیح حذف می‌شوند، رشتهٔ خالی یا بولی به‌جای عدد رد می‌شود. SQLite نوع‌دهی انعطاف‌پذیر دارد؛ نوشتن مستقیم SQL جایگزین اعتبارسنجی API نیست.

نوع float برای حفظ قرارداد تمرین قبلی باقی مانده است. این پروژه ثبت آموزشی هزینه‌هاست و محاسبه یا انتقال پول انجام نمی‌دهد؛ طراحی حسابداری واقعی نیاز به سیاست واحد پول و دقت اعشاری مشخص دارد.

## منابع

- https://docs.sqlalchemy.org/en/21/orm/session_basics.html
- https://alembic.sqlalchemy.org/en/latest/tutorial.html
- https://alembic.sqlalchemy.org/en/latest/autogenerate.html
