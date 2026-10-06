from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


APP_NAME = "JobTrack"
DATABASE_NAME = "jobtrack.db"


def get_data_directory() -> Path:
    """Return the directory used to store JobTrack data."""
    data_directory = Path.home() / "AppData" / "Local" / APP_NAME
    data_directory.mkdir(parents=True, exist_ok=True)

    return data_directory


def get_database_path() -> Path:
    """Return the path to the JobTrack SQLite database."""
    return get_data_directory() / DATABASE_NAME


def create_database_engine() -> Engine:
    """Create the SQLAlchemy engine for the JobTrack database."""
    database_path = get_database_path()
    database_url = f"sqlite:///{database_path.as_posix()}"

    return create_engine(database_url)
