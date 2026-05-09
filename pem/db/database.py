"""Database functionality for the Python Execution Manager (PEM)."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from typing_extensions import Self

logger = logging.getLogger(__name__)


def _get_default_db_path() -> Path:
    """Get the default database path."""
    try:
        from pem.config import get_config

        config = get_config()
        db_path = config.database_path
        if db_path:
            return Path(db_path)
    except Exception:
        pass

    default_path = Path.home() / ".pem" / "pem.db"
    default_path.parent.mkdir(parents=True, exist_ok=True)
    return default_path


class DatabaseConnection:
    """SQLite connection wrapper with SQLAlchemy-like interface."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, query: Any, params: tuple | dict | None = None) -> "ResultProxy":
        """Execute a query."""
        cursor = self._conn.cursor()
        if params is None:
            params = ()
        cursor.execute(query, params)
        return ResultProxy(cursor, self._conn)

    def commit(self) -> None:
        """Commit the transaction."""
        self._conn.commit()

    def rollback(self) -> None:
        """Rollback the transaction."""
        self._conn.rollback()

    def close(self) -> None:
        """Close the connection."""
        self._conn.close()


class ResultProxy:
    """Result wrapper with SQLAlchemy-like interface."""

    def __init__(self, cursor: sqlite3.Cursor, connection: sqlite3.Connection) -> None:
        self._cursor = cursor
        self._connection = connection
        self._rows: list[sqlite3.Row] | None = None

    @property
    def scalars(self) -> "ScalarResultProxy":
        """Return scalar results."""
        return ScalarResultProxy(self._cursor)

    def all(self) -> list[sqlite3.Row]:
        """Return all rows."""
        if self._rows is None:
            self._rows = self._cursor.fetchall()
        return self._rows

    def first(self) -> sqlite3.Row | None:
        """Return first row."""
        rows = self.all()
        return rows[0] if rows else None


class ScalarResultProxy:
    """Scalar result wrapper."""

    def __init__(self, cursor: sqlite3.Cursor) -> None:
        self._cursor = cursor

    def all(self) -> list[Any]:
        """Return all scalar values."""
        return [row[0] for row in self._cursor.fetchall()]

    def first(self) -> Any:
        """Return first scalar value."""
        row = self._cursor.fetchone()
        return row[0] if row else None


class Session:
    """SQLAlchemy-like session interface."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._closed = False

    def execute(self, query: Any, params: tuple | dict | None = None) -> ResultProxy:
        """Execute a query."""
        cursor = self._conn.cursor()
        query_str = str(query) if hasattr(query, "selectable") else query

        if params is None:
            params = ()

        try:
            cursor.execute(query_str, params)
        except Exception as e:
            logger.debug(f"Query: {query_str}, Params: {params}, Error: {e}")
            raise

        return ResultProxy(cursor, self._conn)

    def add(self, obj: Any) -> None:
        """Add an object to the session."""
        from pem.db.models import ExecutionRun, Job

        cursor = self._conn.cursor()

        if isinstance(obj, Job):
            deps_json = json.dumps(obj.dependencies) if obj.dependencies else None
            cursor.execute(
                """INSERT INTO jobs (name, job_type, path, dependencies, python_version, is_enabled)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    obj.name,
                    obj.job_type,
                    obj.path,
                    deps_json,
                    obj.python_version,
                    1 if obj.is_enabled else 0,
                ),
            )
            obj.id = int(cursor.lastrowid or 0)

        elif isinstance(obj, ExecutionRun):
            cursor.execute(
                """INSERT INTO execution_runs (job_id, start_time, end_time, status, exit_code, log_path)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    obj.job_id,
                    obj.start_time.isoformat() if isinstance(obj.start_time, datetime) else obj.start_time,
                    obj.end_time.isoformat() if obj.end_time and isinstance(obj.end_time, datetime) else obj.end_time,
                    obj.status,
                    obj.exit_code,
                    obj.log_path,
                ),
            )
            obj.id = int(cursor.lastrowid or 0)

    def commit(self) -> None:
        """Commit the transaction."""
        self._conn.commit()

    def rollback(self) -> None:
        """Rollback the transaction."""
        self._conn.rollback()

    def refresh(self, obj: Any) -> None:
        """Refresh an object."""
        from pem.db.models import ExecutionRun, Job

        cursor = self._conn.cursor()

        if isinstance(obj, Job):
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (obj.id,))
            row = cursor.fetchone()
            if row:
                obj.name = row["name"]
                obj.job_type = row["job_type"]
                obj.path = row["path"]
                obj.dependencies = json.loads(row["dependencies"]) if row["dependencies"] else None
                obj.python_version = row["python_version"]
                obj.is_enabled = bool(row["is_enabled"])

        elif isinstance(obj, ExecutionRun):
            cursor.execute("SELECT * FROM execution_runs WHERE id = ?", (obj.id,))
            row = cursor.fetchone()
            if row:
                obj.job_id = row["job_id"]
                obj.start_time = row["start_time"]
                obj.end_time = row["end_time"]
                obj.status = row["status"]
                obj.exit_code = row["exit_code"]
                obj.log_path = row["log_path"]

    def delete(self, obj: Any) -> None:
        """Delete an object."""
        from pem.db.models import ExecutionRun, Job

        cursor = self._conn.cursor()

        if isinstance(obj, Job):
            cursor.execute("DELETE FROM jobs WHERE id = ?", (obj.id,))
        elif isinstance(obj, ExecutionRun):
            cursor.execute("DELETE FROM execution_runs WHERE id = ?", (obj.id,))

    def close(self) -> None:
        """Close the session."""
        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.rollback()
        self.close()


class Database:
    """Database manager for PEM."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else _get_default_db_path()
        self._connection: sqlite3.Connection | None = None

    def _ensure_connection(self) -> sqlite3.Connection:
        """Ensure connection exists."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                timeout=20,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            self._apply_pragmas(self._connection)
            self._init_schema(self._connection)
        return self._connection

    def _apply_pragmas(self, conn: sqlite3.Connection) -> None:
        """Apply SQLite optimization pragmas."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=268435456")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA auto_vacuum=INCREMENTAL")
        conn.commit()

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        """Initialize database schema."""
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                job_type TEXT NOT NULL,
                path TEXT NOT NULL,
                dependencies TEXT,
                python_version REAL,
                is_enabled INTEGER DEFAULT 1
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                status TEXT NOT NULL,
                exit_code INTEGER,
                log_path TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_name_enabled ON jobs(name, is_enabled)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_type_enabled ON jobs(job_type, is_enabled)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_execution_runs_job_start ON execution_runs(job_id, start_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_execution_runs_status ON execution_runs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_run_job_status ON execution_runs(job_id, status)")

        conn.commit()

    def get_session(self) -> Session:
        """Get a database session."""
        conn = self._ensure_connection()
        return Session(conn)

    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


_db: Database | None = None


def get_database() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


class SessionLocal:
    """Async session factory for backward compatibility."""

    def __new__(cls) -> Session:
        db = get_database()
        return db.get_session()

    async def __aenter__(self) -> Session:
        db = get_database()
        return db.get_session()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


async def create_db_and_tables() -> None:
    """Creates the database and tables if they don't exist."""
    db = get_database()
    db._ensure_connection()
