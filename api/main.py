from fastapi import FastAPI
from api.config import get_settings

# Load centralized settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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
