from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from pem.settings import DATABASE_URL

Base = declarative_base()

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_db_and_tables() -> None:
    """Creates the database and tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
