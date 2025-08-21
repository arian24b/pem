"""Database Models are defined here."""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pem.db.database import Base


class Job(Base):
    """Represents a job that can be executed."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)  # Use Text for longer paths
    dependencies: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    python_version: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    runs: Mapped[list["ExecutionRun"]] = relationship(
        "ExecutionRun",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="select",  # Optimize loading strategy
    )

    # Performance indexes
    __table_args__ = (
        Index("idx_job_name_enabled", "name", "is_enabled"),
        Index("idx_job_type_enabled", "job_type", "is_enabled"),
    )


class ExecutionRun(Base):
    """Represents a single execution of a job."""

    __tablename__ = "execution_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(UTC), index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_path: Mapped[str | None] = mapped_column(Text, nullable=True)  # Use Text for longer paths

    job: Mapped["Job"] = relationship(
        "Job",
        back_populates="runs",
        lazy="select",  # Optimize loading strategy
    )

    # Performance indexes
    __table_args__ = (
        Index("idx_run_job_start", "job_id", "start_time"),
        Index("idx_run_status_start", "status", "start_time"),
        Index("idx_run_job_status", "job_id", "status"),
    )
