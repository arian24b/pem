#!/usr/bin/env python3
"""Performance test script for PEM."""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the pem directory to path
sys.path.insert(0, str(Path(__file__).parent))

from pem.db.database import init_db, create_all_tables
from pem.db.models import Job
from pem.core.executor import JobExecutor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_database_performance():
    """Test database performance."""
    logger.info("Testing database performance...")
    
    start_time = time.time()
    
    # Initialize database
    await init_db()
    await create_all_tables()
    
    setup_time = time.time() - start_time
    logger.info(f"Database setup time: {setup_time:.3f}s")
    
    # Test job creation performance
    start_time = time.time()
    
    # Create test jobs
    for i in range(100):
        job = Job(
            command=f"echo 'Test job {i}'",
            working_directory="/tmp",
            status="pending"
        )
        # In a real scenario, you'd save to the database here
    
    creation_time = time.time() - start_time
    logger.info(f"100 job objects creation time: {creation_time:.3f}s")


async def test_executor_performance():
    """Test executor performance."""
    logger.info("Testing executor performance...")
    
    executor = JobExecutor()
    
    # Test simple command execution
    start_time = time.time()
    
    job = Job(
        id=1,
        command="echo 'Hello, World!'",
        working_directory="/tmp",
        status="pending"
    )
    
    result = await executor.execute_job(job)
    
    execution_time = time.time() - start_time
    logger.info(f"Simple job execution time: {execution_time:.3f}s")
    logger.info(f"Job result: {result}")
    
    # Test concurrent execution
    logger.info("Testing concurrent execution...")
    start_time = time.time()
    
    jobs = []
    for i in range(10):
        job = Job(
            id=i + 2,
            command=f"sleep 0.1 && echo 'Job {i}'",
            working_directory="/tmp",
            status="pending"
        )
        jobs.append(job)
    
    # Execute jobs concurrently
    tasks = [executor.execute_job(job) for job in jobs]
    results = await asyncio.gather(*tasks)
    
    concurrent_time = time.time() - start_time
    logger.info(f"10 concurrent jobs execution time: {concurrent_time:.3f}s")
    logger.info(f"Successful executions: {sum(1 for r in results if r and r.get('success'))}")


async def main():
    """Run performance tests."""
    logger.info("Starting PEM performance tests...")
    
    try:
        await test_database_performance()
        await test_executor_performance()
        
        logger.info("Performance tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Performance test failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
