"""Add users, revocable sessions, and expense ownership without claiming legacy rows."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table("auth_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_sessions_user"), nullable=False),
        sa.Column("refresh_hash", sa.String(64), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
    )
    with op.batch_alter_table("expenses", table_kwargs={"sqlite_autoincrement": True}) as batch:
        batch.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_expenses_owner", "users", ["owner_id"], ["id"])
        batch.create_index("ix_expenses_owner_id", ["owner_id"])


def downgrade():
    with op.batch_alter_table("expenses", table_kwargs={"sqlite_autoincrement": True}) as batch:
        batch.drop_index("ix_expenses_owner_id")
        batch.drop_constraint("fk_expenses_owner", type_="foreignkey")
        batch.drop_column("owner_id")
    op.drop_table("auth_sessions")
    op.drop_table("users")
