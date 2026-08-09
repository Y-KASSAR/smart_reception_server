from pathlib import Path
from sqlalchemy import create_engine, text
from typing import Generator
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from config.settings import settings
from database.models import Base
from config.logging_config import get_logger

logger = get_logger(__name__)

db_path = Path(settings.database.full_path)
db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{db_path}",
    connect_args= {"check_same_thread": False},
    echo = False
)

SessionLocal = sessionmaker(autocommit=False, bind=engine)

# Columns added to an already-existing table after its first deployment.
# `Base.metadata.create_all()` only creates missing TABLES, never adds
# columns to a table that already exists — so a DB created before these
# fields existed needs them bolted on explicitly. Keyed by table name.
_ADDED_COLUMNS = {
    "guests": [
        ("company", "VARCHAR(200)"),
        ("source", "VARCHAR(50)"),
    ],
}


def _run_column_migrations():
    """Idempotently ALTER TABLE ADD COLUMN for any column in _ADDED_COLUMNS
    missing from the live DB. Safe to run on every startup."""
    with engine.connect() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            existing = {
                row[1]  # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
                for row in conn.execute(text(f"PRAGMA table_info({table})"))
            }
            if not existing:
                continue  # table doesn't exist yet — create_all() will make it with all columns
            for col_name, col_type in columns:
                if col_name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                logger.info(f"Migrated schema: added {table}.{col_name}")
        conn.commit()


def init_db():
    logger.info(f"Initializing database at {db_path}")
    Base.metadata.create_all(bind=engine)
    _run_column_migrations()
    logger.info("Database tables created successfully")

def reset_db():
    logger.warning("Resetting database - ALL DATA WILL BE LOST" )
    Base.metadata.drop_all(bind= engine)
    Base.metadata.create_all(bind=engine)
    logger.info("Database reset completed")

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()  # adjusted
        raise
    finally:
        db.close()

@contextmanager
def get_db_session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        