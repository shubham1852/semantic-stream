"""
main.py
=======
FastAPI application entry point for SemanticStream.

Responsibilities:
  - Create and configure the FastAPI application instance
  - Register all API routers under the /api/v1 prefix
  - Mount WebSocket endpoint at /ws/live
  - Configure CORS middleware
  - Register global exception handlers
  - Initialise the database on startup
  - Expose /health endpoint for Docker health-checks

This file contains ZERO business logic.  All logic lives in services/.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import settings
from backend.core.exceptions import (
    AnalysisError,
    BandwidthProfileError,
    DetectionError,
    ExperimentNotFoundError,
    FFmpegError,
    FileTooLargeError,
    InvalidVideoFormatError,
    JobNotFoundError,
    ModelLoadError,
    ReportGenerationError,
    SemanticStreamError,
    StorageError,
    UploadError,
    VideoNotFoundError,
    VideoProcessingError,
    WebSocketError,
)
from backend.core.logging_config import configure_logging, get_logger
from backend.database.database import init_db

# ── Routers ────────────────────────────────────────────────────────────────────
from backend.api.routes.upload import router as upload_router
from backend.api.routes.analyze import router as analyze_router
from backend.api.routes.results import router as results_router
from backend.api.routes.stream import router as stream_router
from backend.api.routes.experiment import router as experiment_router
from backend.api.routes.history import router as history_router
from backend.api.routes.bandwidth import router as bandwidth_router
from backend.api.routes.report import router as report_router
from backend.api.websocket import router as ws_router

configure_logging()
logger = get_logger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Runs on startup: initialise database tables.
    Runs on shutdown: log graceful shutdown.
    """
    logger.info(
        "semanticstream.startup",
        version=settings.APP_VERSION,
        env_debug=settings.DEBUG,
    )
    await init_db()
    yield
    logger.info("semanticstream.shutdown")


# ── Application factory ────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Returns:
        Configured ``FastAPI`` instance ready to be served by Uvicorn.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "SemanticStream — Semantic-Aware Adaptive Video Streaming Framework "
            "with Bandwidth-Aware Region Priority Encoding.\n\n"
            "VIT BITE314L Multimedia Systems Project · Fall 2026-27"
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    prefix = settings.API_PREFIX

    app.include_router(upload_router,     prefix=prefix, tags=["Upload"])
    app.include_router(analyze_router,    prefix=prefix, tags=["Analyze"])
    app.include_router(results_router,    prefix=prefix, tags=["Results"])
    app.include_router(stream_router,     prefix=prefix, tags=["Stream"])
    app.include_router(experiment_router, prefix=prefix, tags=["Experiment"])
    app.include_router(history_router,    prefix=prefix, tags=["History"])
    app.include_router(bandwidth_router,  prefix=prefix, tags=["Bandwidth"])
    app.include_router(report_router,     prefix=prefix, tags=["Report"])
    app.include_router(ws_router,         tags=["WebSocket"])

    # ── Exception handlers ────────────────────────────────────────────────────
    _register_exception_handlers(app)

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Register domain exception → HTTP response mappers."""

    @app.exception_handler(VideoNotFoundError)
    @app.exception_handler(JobNotFoundError)
    @app.exception_handler(ExperimentNotFoundError)
    async def not_found_handler(request: Request, exc: SemanticStreamError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(FileTooLargeError)
    @app.exception_handler(InvalidVideoFormatError)
    async def bad_request_handler(request: Request, exc: SemanticStreamError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(ModelLoadError)
    async def model_error_handler(request: Request, exc: SemanticStreamError) -> JSONResponse:
        logger.error("model.load.failed", detail=exc.detail)
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(SemanticStreamError)
    async def generic_domain_error_handler(
        request: Request, exc: SemanticStreamError
    ) -> JSONResponse:
        logger.error("domain.error", type=type(exc).__name__, message=exc.message, detail=exc.detail)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled.error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "An unexpected error occurred.", "detail": str(exc)},
        )


# ── Application singleton ─────────────────────────────────────────────────────
app = create_app()


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], summary="Health check endpoint")
async def health_check() -> dict:
    """Return application health status.

    Used by Docker Compose health-check and load balancers.

    Returns:
        Dict with status and version information.
    """
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# ── Dev entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
