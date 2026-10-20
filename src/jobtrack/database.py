from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session

APP_NAME = "JobTrack"
DATABASE_NAME = "jobtrack.db"


def get_data_directory() -> Path:
    """Return the production storage directory, creating it when requested."""
    directory = Path.home() / "AppData" / "Local" / APP_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_database_path() -> Path:
    return get_data_directory() / DATABASE_NAME


@lru_cache(maxsize=None)
def _engine(path: Path) -> Engine:
    return create_engine(URL.create("sqlite", database=str(path)))


def create_database_engine(database_path: Path | None = None) -> Engine:
    """Reuse an engine by path; explicit paths never resolve production storage."""
    path = database_path if database_path is not None else get_database_path()
    return _engine(Path(path).resolve())


def initialize_database(database_path: Path | None = None) -> None:
    from jobtrack.models import Base
    Base.metadata.create_all(create_database_engine(database_path))


def create_session(database_path: Path | None = None) -> Session:
    """Caller closes session; service writers commit or roll back each operation."""
    return Session(create_database_engine(database_path))
