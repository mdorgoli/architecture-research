from sqlalchemy import CheckConstraint, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("length(trim(description)) > 0", name="ck_expenses_description_nonempty"),
        CheckConstraint("amount > 0 AND amount <= 1.7976931348623157e308", name="ck_expenses_amount_positive_finite"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
