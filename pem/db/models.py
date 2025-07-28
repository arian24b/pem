import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    project_path = Column(String, nullable=False)
    is_enabled = Column(Boolean, default=True)

    runs = relationship("ExecutionRun", back_populates="project", cascade="all, delete-orphan")


class ExecutionRun(Base):
    __tablename__ = "execution_runs"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime)
    status = Column(String, nullable=False)
    exit_code = Column(Integer)
    log_path = Column(String)

    project = relationship("Project", back_populates="runs")
