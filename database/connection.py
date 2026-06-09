from pathlib import Path
from sqlalchemy import create_engine
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

def init_db():
    logger.info(f"Initializing database at {db_path}")
    Base.metadata.create_all(bind=engine)
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
        