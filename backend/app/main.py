import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.scheduler.cron_runner import cron_scheduler
from app.routers import products, settings as settings_router, logs, cron

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("threads_agent.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing SQLite database tables...")
    await init_db()

    logger.info("Verifying sensitive credentials encryption at rest...")
    from app.database import AsyncSessionLocal
    from app.security import migrate_unencrypted_settings
    async with AsyncSessionLocal() as db:
        await migrate_unencrypted_settings(db)
    
    logger.info("Starting background cron scheduler...")
    cron_scheduler.start()
    await cron_scheduler.reload_schedule()
    
    yield
    
    logger.info("Shutting down cron scheduler...")
    cron_scheduler.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Autonomous Threads Affiliate Marketing Agent with Playwright Tool Calling",
    version="1.0.0",
    lifespan=lifespan
)

# Allow CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(logs.router)
app.include_router(products.router)
app.include_router(settings_router.router)
app.include_router(cron.router)


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "database": "SQLite",
        "scheduler_active": cron_scheduler.scheduler.running
    }
