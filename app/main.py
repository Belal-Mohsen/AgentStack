import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langfuse import Langfuse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Our Modules
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.limiter import limiter
from app.core.config.logging import get_logger
from app.core.metrics import setup_metrics
from app.core.middleware import LoggingContextMiddleware, MetricsMiddleware
from app.services.database import database_service

# Load environment variables
load_dotenv()
# Get logger
logger = get_logger(__name__)

# Initialize Langfuse globally for background tracing
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle application startup and shutdown events.
    This replaces the old @app.on_event pattern.
    """
    # Startup Logic
    logger.info(
        "application_startup",
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        api_prefix=settings.API_V1_STR,
        environment=settings.ENVIRONMENT.value
    )
    
    yield # Application runs here
    
    # Shutdown Logic (Graceful cleanup)
    logger.info("application_shutdown")
    # Here you would close DB connections or flush Langfuse buffers
    langfuse.flush()
# Initialize the Application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AgentStack API",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# 1. Set up Prometheus metrics
setup_metrics(app)

# 2. Add logging context middleware (First to bind context, last to clear it)
app.add_middleware(LoggingContextMiddleware)

# 3. Add custom metrics middleware (Tracks latency)
app.add_middleware(MetricsMiddleware)

# 4. Set up CORS (Cross-Origin Resource Sharing)
# Critical for allowing your Frontend (React/Vue) to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Connect Rate Limiter to the App state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler for validation errors.
    Formats Pydantic errors into a user-friendly JSON structure.
    """
    # Log the error for debugging (warn level, not error, as it's usually client fault)
    logger.warning(
        "validation_error",
        path=request.url.path,
        errors=str(exc.errors()),
    )

    # Reformat "loc" (location) to be readable
    # e.g. ["body", "email"] -> "email"
    formatted_errors = []
    for error in exc.errors():
        loc = " -> ".join([str(loc_part) for loc_part in error["loc"] if loc_part != "body"])
        formatted_errors.append({"field": loc, "message": error["msg"]})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": formatted_errors},
    )

# Include the main API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["root"][0])
async def root(request: Request):
    """
    Root endpoint for basic connectivity tests.
    """
    logger.info("root_endpoint_called")
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT.value,
        "docs_url": "/docs",
    }

@app.get("/health")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["health"][0])
async def health_check(request: Request) -> Dict[str, Any]:
    """
    Production Health Check.
    Validates that the App AND the Database are responsive.
    """
    # Check database connectivity
    db_healthy = await database_service.health_check()
    
    status_code = status.HTTP_200_OK if db_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if db_healthy else "degraded",
            "components": {
                "api": "healthy", 
                "database": "healthy" if db_healthy else "unhealthy"
            },
            "timestamp": datetime.now().isoformat(),
        }
    )