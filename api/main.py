import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import get_settings
from llm.provider import check_llm_config

# Routers
from api.routers import clinics, ingest, records

# Middleware
from api.middleware.audit import AuditMiddleware

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

# Enable Audit Middleware (request-level observability)
app.add_middleware(AuditMiddleware)

# CORS for the browser UI: explicit origin allowlist, no credentials (cookies), only the methods/headers the UI uses.
# Authorization carries the staff bearer token for the Staff Review UI (#31); the backend still authorizes every call.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Router Registration
app.include_router(
    ingest.router,
    prefix="/api",
    tags=["Ingest"],
)
app.include_router(
    clinics.router,
    prefix="/api",
    tags=["Staff"],
)
app.include_router(
    records.router,
    prefix="/api",
    tags=["Staff"],
)

# Lifecycle Events
@app.on_event("startup")
def on_startup():
    logger.info(f"🚀 {settings.app_name} starting up...")
    logger.info(f"Environment: {settings.app_env}")
    # Refuse to start in real mode without provider configuration (never fall back to mock)
    check_llm_config(settings)
    logger.info(f"LLM mode: {settings.llm_mode}")


@app.on_event("shutdown")
def on_shutdown():
    logger.info(f"🛑 {settings.app_name} shutting down...")

# Basic system health check. Exposes only the execution mode, never provider configuration.
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
        "llm_mode": settings.llm_mode,
    }

# Root
@app.get("/", tags=["System"])
def root():
    return {
        "message": "Healthcare AI Platform API is running",
        "docs": "/docs",
    }
