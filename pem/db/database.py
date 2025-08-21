"""Database functionality for the Python Execution Manager (PEM)."""

import logging

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from pem.settings import DATABASE_URL
from pem.performance_config import DATABASE_PERFORMANCE_CONFIG, get_optimized_config

Base = declarative_base()
logger = logging.getLogger(__name__)

# Performance optimizations for SQLite
engine = create_async_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 20,
    },
    # Connection pool settings for better performance
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=3600,
    # Performance tuning
    echo=False,
    future=True,
)

SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance."""
    if "sqlite" in str(dbapi_connection):
        cursor = dbapi_connection.cursor()
        # Enable WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        # Increase cache size (negative = KB, positive = pages)
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        # Synchronous mode for performance vs durability balance
        cursor.execute("PRAGMA synchronous=NORMAL")
        # Memory-mapped I/O
        cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
        # Optimize for faster writes
        cursor.execute("PRAGMA temp_store=MEMORY")
        # Foreign key support
        cursor.execute("PRAGMA foreign_keys=ON")
        # Auto vacuum for maintenance
        cursor.execute("PRAGMA auto_vacuum=INCREMENTAL")
        cursor.close()


async def create_db_and_tables() -> None:
    """Creates the database and tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create performance indexes
        await conn.run_sync(_create_performance_indexes)


def _create_performance_indexes(conn):
    """Create additional performance indexes."""
    try:
        # Index for job lookups by name (most common operation)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_name_enabled ON jobs(name, is_enabled)")
        # Index for execution runs by job_id and start_time
        conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_runs_job_start ON execution_runs(job_id, start_time)")
        # Index for execution runs by status for filtering
        conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_runs_status ON execution_runs(status)")
        # Composite index for common queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_type_enabled ON jobs(job_type, is_enabled)")
    except Exception as e:
        # Indexes might already exist, log but continue
        logger.debug(f"Index creation failed (likely already exists): {e}")
