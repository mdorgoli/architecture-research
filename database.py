import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
import sqlite3
from sqlalchemy.orm import DeclarativeBase, sessionmaker


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, record):
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    pass


default_path = Path(__file__).resolve().parent / "expenses.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{default_path.as_posix()}")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    with SessionLocal() as session:
        yield session
