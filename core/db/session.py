import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import config
from core.log import get_logger

logger = get_logger(__name__)


class DBConnect:
    """The engine and session factory for one database URL. Alembic migrations make the schema."""

    def __init__(self, db_url="sqlite:///./data/user.db") -> None:
        self.SQLALCHEMY_DATABASE_URL = db_url
        self._ensure_db_directory()
        if self.SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
            self.engine = create_engine(self.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
        else:
            self.engine = create_engine(self.SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def _ensure_db_directory(self):
        """Create the directory of a SQLite database file if it does not exist."""
        if self.SQLALCHEMY_DATABASE_URL.startswith("sqlite:///"):
            db_dir = os.path.dirname(os.path.normpath(self.SQLALCHEMY_DATABASE_URL[10:]))
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")

    def get_db(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()


db_connect = DBConnect(config.DATABASE_URL)


@contextmanager
def session() -> Iterator[Session]:
    """A database session that commits on success, rolls back on an error and always closes."""
    db = db_connect.SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
