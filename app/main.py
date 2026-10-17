from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database.database import init_db, SessionLocal
from app.api.routes import router
from app.api.krishi_routes import router as krishi_router
from app.services.ingestion import IngestionService
from app.database.krishi_repository import KrishiRepository
from app.services.agmarknet import AgmarknetService
from app.services.alerts import AlertService

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
)
logger = logging.getLogger("krishibhav_app")

scheduler = BackgroundScheduler(daemon=True)


def scheduled_alert_job():
    """Background recurring evaluation of farmer price threshold alerts."""
    logger.info("[Scheduler] Starting price threshold alert evaluation cycle...")
    db = SessionLocal()
    try:
        service = AlertService(db=db)
        summary = service.evaluate_active_alerts()
        logger.info(f"[Scheduler] Alert evaluation complete: {summary}")
    except Exception as exc:
        logger.error(f"[Scheduler] Alert evaluation error: {exc}", exc_info=True)
    finally:
        db.close()


def scheduled_ingestion_job():
    """Background scheduled job for recurring news collection."""
    logger.info("[Scheduler] Starting scheduled news collection cycle...")
    db = SessionLocal()
    try:
        service = IngestionService(db=db, enable_ai=True)
        results = service.run_pipeline(include_news_api=True, include_rss=True)
        logger.info(f"[Scheduler] Completed collection: {results['inserted']} new articles.")
    except Exception as exc:
        logger.error(f"[Scheduler] Scheduled ingestion encountered an error: {exc}", exc_info=True)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan manager for database initialization, data seeding, and scheduler lifecycle."""
    logger.info("Initializing system database schema...")
    init_db()

    # Seed verified Agmarknet dataset into authoritative storage
    db = SessionLocal()
    try:
        agmark_svc = AgmarknetService(KrishiRepository(db))
        agmark_svc.seed_verified_dataset()
    except Exception as exc:
        logger.warning(f"Could not seed initial Agmarknet dataset: {exc}")
    finally:
        db.close()

    # Configure background scheduler
    if settings.ALERT_POLL_INTERVAL_MINUTES > 0:
        logger.info(f"Scheduling price alert evaluation every {settings.ALERT_POLL_INTERVAL_MINUTES}m...")
        scheduler.add_job(
            scheduled_alert_job,
            "interval",
            minutes=settings.ALERT_POLL_INTERVAL_MINUTES,
            id="recurring_alert_poll",
            replace_existing=True,
        )

    if settings.INGESTION_INTERVAL_MINUTES > 0:
        logger.info(f"Starting background scheduler (interval: {settings.INGESTION_INTERVAL_MINUTES}m)...")
        scheduler.add_job(
            scheduled_ingestion_job,
            "interval",
            minutes=settings.INGESTION_INTERVAL_MINUTES,
            id="recurring_news_ingestion",
            replace_existing=True,
        )
    
    scheduler.start()

    yield

    if scheduler.running:
        logger.info("Shutting down background scheduler gracefully...")
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="KrishiBhav — Agricultural Market Intelligence API",
    version="1.0.0",
    description="Authoritative agricultural market intelligence platform for Indian farmers, traders, and stakeholders.",
    lifespan=lifespan,
)

# Explicit CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list + ["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PUT", "OPTIONS"],
    allow_headers=["*"],
)

# Attach API routes
app.include_router(krishi_router)
app.include_router(router)


@app.get("/")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "health_url": "/health",
        "api_prefix": "/api",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)
