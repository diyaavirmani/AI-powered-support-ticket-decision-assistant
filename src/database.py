"""SQLAlchemy engine, sessions, and database initialization."""

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def init_db() -> None:
    from src import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    if engine.dialect.name == "sqlite":
        with engine.connect() as conn:
            cursor = conn.execute(text("PRAGMA table_info(decisions)"))
            columns = {row[1] for row in cursor.fetchall()}
            if "retrieval_latency_ms" not in columns:
                conn.execute(text("ALTER TABLE decisions ADD COLUMN retrieval_latency_ms FLOAT"))
            if "llm_latency_ms" not in columns:
                conn.execute(text("ALTER TABLE decisions ADD COLUMN llm_latency_ms FLOAT"))
            if "guardrail_triggered" not in columns:
                conn.execute(text("ALTER TABLE decisions ADD COLUMN guardrail_triggered BOOLEAN DEFAULT 0"))
            if "human_override_action" not in columns:
                conn.execute(text("ALTER TABLE decisions ADD COLUMN human_override_action VARCHAR(64)"))
            if "human_override_reason" not in columns:
                conn.execute(text("ALTER TABLE decisions ADD COLUMN human_override_reason TEXT"))
            if "reviewed_at" not in columns:
                conn.execute(text("ALTER TABLE decisions ADD COLUMN reviewed_at DATETIME"))
            conn.commit()


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
