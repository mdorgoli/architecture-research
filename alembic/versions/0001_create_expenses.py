"""Create the expense table."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.CheckConstraint("length(trim(description)) > 0", name="ck_expenses_description_nonempty"),
        sa.CheckConstraint("amount > 0 AND amount <= 1.7976931348623157e308", name="ck_expenses_amount_positive_finite"),
        sa.PrimaryKeyConstraint("id"),
        sqlite_autoincrement=True,
    )


def downgrade():
    op.drop_table("expenses")
