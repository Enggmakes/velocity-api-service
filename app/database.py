import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Create engine with connect_args for SQLite WAL mode and foreign keys
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

# Enable SQLite WAL (Write-Ahead Logging) and foreign key constraints for high concurrency
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for obtaining database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all database tables and apply missing column migrations."""
    Base.metadata.create_all(bind=engine)

    # Safe column migration for existing SQLite databases
    if settings.DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            for table in ["activity_events", "heartbeats", "github_events"]:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN api_key_id INTEGER;"))
                    conn.commit()
                except Exception:
                    pass  # Column already exists
