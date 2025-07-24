from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from pem.core.executor import JobExecutor  # Your executor class

# --- App and Scheduler Initialization ---
app = FastAPI(title="pem - Python Execution Manager API")
scheduler = AsyncIOScheduler()


# --- Example of a scheduled job ---
async def run_scheduled_job(project_name: str, project_path: str) -> None:
    """The function that APScheduler will call."""
    executor = JobExecutor(project_name, project_path)
    await executor.execute()
    # Logic to update database would go here


@app.on_event("startup")
async def startup_event() -> None:
    """Configure and start the scheduler on app startup."""
    jobstores = {"default": SQLAlchemyJobStore(url="sqlite:///pem.db")}
    scheduler.configure(jobstores=jobstores)

    # Here you would load jobs from your database and add them to the scheduler
    # Example:
    # scheduler.add_job(
    #     run_scheduled_job,
    #     'cron',
    #     args=["My Scheduled Project", "/path/to/project"],
    #     id='project_1',
    #     day_of_week='mon-fri',
    #     hour=10,
    #     minute=30,
    #     replace_existing=True
    # )

    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    scheduler.shutdown()


# --- API Endpoints ---
@app.get("/")
async def root():
    return {"message": "Welcome to pem - Python Execution Manager"}


# Your other FastAPI routers would be included here
# from pem.api import routers
# app.include_router(routers.router)
