import logging
from fastapi import FastAPI
from api.config import get_settings
# Routers
from api.routers import ingest

# Load centralized settings
settings = get_settings()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("api.main")

# FastAPI App Initialization
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
# Router Registration
app.include_router(
    ingest.router,
    prefix="/api",
    tags=["Ingest"],
)

# Lifecycle Events
@app.on_event("startup")
def on_startup():
    logger.info(f"🚀 {settings.app_name} starting up...")
    logger.info(f"Environment: {settings.app_env}")


@app.on_event("shutdown")
def on_shutdown():
    logger.info(f"🛑 {settings.app_name} shutting down...")

# Basic system health check.
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
    }

# Root
@app.get("/", tags=["System"])
def root():
    return {
        "message": "Healthcare AI Platform API is running",
        "docs": "/docs",
    }
