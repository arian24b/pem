from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pem.db.models import Base

DATABASE_URL = "sqlite:///pem.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_db_and_tables():
    """Creates the database and tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
