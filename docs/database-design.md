# Schema نسخهٔ احراز هویت

نمودار فعلی: [auth-schema.drawio](auth-schema.drawio). نمودار expense-database.drawio مربوط به نسخهٔ قبلی 0001 نگه داشته شده است.

| جدول | ستون‌ها و قیدها |
|---|---|
| users | id کلید اصلی؛ username رشتهٔ ۶۴ کاراکتری یکتا؛ password_hash متن Argon2؛ هر دو NOT NULL |
| auth_sessions | id رشتهٔ ۶۴ کاراکتری کلید اصلی؛ user_id کلید خارجی users؛ refresh_hash و csrf_hash رشتهٔ ۶۴ کاراکتری؛ expires_at زمان Unix؛ revoked بولی؛ همه NOT NULL |
| expenses | id عددی AUTOINCREMENT؛ description متن غیرخالی؛ amount مثبت و متناهی؛ owner_id کلید خارجی users و دارای index؛ nullable برای حفظ هزینه‌های قدیمی |
| alembic_version | نسخهٔ schema؛ مستقل از داده‌های کسب‌وکار |

هر کاربر چند هزینه و چند نشست دارد. شناسهٔ نشست تصادفی است و شناسهٔ کاربر از JWT معتبر و نشست فعال استخراج می‌شود. کلیدهای خارجی SQLite با PRAGMA foreign_keys=ON فعال‌اند.

Engine و Session در database.py تعریف می‌شوند؛ هر درخواست Session جدا دارد. نوشتن‌ها commit می‌شوند و Session پس از درخواست بسته می‌شود. مدل‌ها در models.py و قرارداد ورودی/خروجی هزینه در schemas.py هستند. نوع float طبق تمرین قبلی حفظ شده است و برای حسابداری دقیق نیازمند تصمیم جداگانه دربارهٔ پول و دقت است.

0001 جدول هزینه را می‌سازد؛ 0002 جدول کاربران، نشست‌ها و owner_id را اضافه می‌کند. API از create_all استفاده نمی‌کند. هزینه‌های موجود حفظ می‌شوند و بدون مالک می‌مانند؛ API آن‌ها را به کسی نشان نمی‌دهد. downgrade 0001 کاربران، نشست‌ها و مالکیت را حذف می‌کند؛ فقط روی نسخهٔ آزمایشی یا پس از پشتیبان‌گیری و تصمیم آگاهانه اجرا شود.

منابع: [SQLAlchemy Session](https://docs.sqlalchemy.org/en/21/orm/session_basics.html)، [Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
