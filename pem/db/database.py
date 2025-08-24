"""Database functionality for the Python Execution Manager (PEM)."""

import logging

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from pem.settings import DATABASE_URL, get_database_config, get_optimized_config

Base = declarative_base()
logger = logging.getLogger(__name__)

# Get optimized configuration
config = get_optimized_config()
db_config = get_database_config()

# Performance optimizations for SQLite
engine = create_async_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 20,
    },
    # Use dynamic configuration
    pool_size=db_config["pool_size"],
    max_overflow=db_config["max_overflow"],
    pool_pre_ping=db_config["pool_pre_ping"],
    pool_recycle=db_config["pool_recycle"],
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
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """Set SQLite pragmas for better performance."""
    if "sqlite" in str(dbapi_connection):
        cursor = dbapi_connection.cursor()
        # Use dynamic configuration
        db_config = get_database_config()

        # Enable WAL mode for better concurrency
        cursor.execute(f"PRAGMA journal_mode={db_config['journal_mode']}")
        # Dynamic cache size based on system resources
        cursor.execute(f"PRAGMA cache_size={db_config['cache_size']}")
        # Synchronous mode for performance vs durability balance
        cursor.execute(f"PRAGMA synchronous={db_config['synchronous']}")
        # Memory-mapped I/O with dynamic size
        cursor.execute(f"PRAGMA mmap_size={db_config['mmap_size']}")
        # Optimize for faster writes
        cursor.execute(f"PRAGMA temp_store={db_config['temp_store']}")
        # Foreign key support
        cursor.execute(f"PRAGMA foreign_keys={db_config['foreign_keys']}")
        # Auto vacuum for maintenance
        cursor.execute(f"PRAGMA auto_vacuum={db_config['auto_vacuum']}")
        cursor.close()


async def create_db_and_tables() -> None:
    """Creates the database and tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create performance indexes
        await conn.run_sync(_create_performance_indexes)


def _create_performance_indexes(conn) -> None:
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
