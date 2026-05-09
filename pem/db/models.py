"""Database Models are defined here."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:
    """Represents a job that can be executed."""

    name: str
    job_type: str
    path: str
    dependencies: list[str] | None = None
    python_version: float | None = None
    is_enabled: bool = True
    id: int = field(default=0)


@dataclass
class ExecutionRun:
    """Represents a single execution of a job."""

    job_id: int
    start_time: datetime | str
    status: str
    end_time: datetime | str | None = None
    exit_code: int | None = None
    log_path: str | None = None
    id: int = field(default=0)
