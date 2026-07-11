"""Forensic Wace REST API.

Stateless by design: the session is a JWT cookie, every request carries the
backup it refers to; there is no per-client server-side state. OpenAPI docs
are served at ``/docs``. Deployment is same-origin (nginx / vite proxy
``/api``), so no CORS middleware is installed.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from forensicwace_core.config import get_settings
from forensicwace_core.exceptions import (
    BackupNotFoundError,
    ConfigurationError,
    ExtractionError,
    InvalidArchiveError,
    InvalidIdentifierError,
    StorageError,
    UnknownSchemaError,
    UnsupportedCapabilityError,
)

from .auth import ensure_bootstrap_admin, get_current_user
from .routers import analyses, analyzers, auth, backups, chats_android, chats_ios, health, projects, reports, schemas, users

logger = logging.getLogger(__name__)

_ERROR_STATUS = {
    InvalidIdentifierError: 400,
    BackupNotFoundError: 404,
    ExtractionError: 422,
    InvalidArchiveError: 422,
    StorageError: 502,
    ConfigurationError: 503,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().database_url:
        from forensicwace_core.analysis.registry import sync_builtin_analyzers
        from forensicwace_core.resultsdb.engine import init_db

        try:
            init_db()
            sync_builtin_analyzers()
            ensure_bootstrap_admin()
        except Exception:
            logger.exception("Results database unavailable — analysis endpoints will fail until it is reachable")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Forensic Wace API",
        description="WhatsApp forensic analysis platform — REST API",
        version="2.0.0a1",
        lifespan=lifespan,
    )

    for exc_type, status_code in _ERROR_STATUS.items():
        app.add_exception_handler(exc_type, _domain_error_handler(status_code))
    app.add_exception_handler(UnknownSchemaError, _unknown_schema_handler)
    app.add_exception_handler(UnsupportedCapabilityError, _unsupported_capability_handler)

    # Prometheus metrics at /metrics (scraped via the pod annotations set by
    # the Helm chart).
    Instrumentator(excluded_handlers=["/metrics", "/healthz", "/readyz"]).instrument(app).expose(app)

    app.include_router(health.router)  # liveness probes stay public

    prefix = "/api/v1"
    # every route below requires a session; /auth/login manages its own access
    protected = [Depends(get_current_user)]
    app.include_router(auth.router, prefix=prefix)
    app.include_router(backups.router, prefix=prefix, dependencies=protected)
    app.include_router(chats_ios.router, prefix=prefix, dependencies=protected)
    app.include_router(chats_android.router, prefix=prefix, dependencies=protected)
    app.include_router(analyses.router, prefix=prefix, dependencies=protected)
    app.include_router(analyzers.router, prefix=prefix, dependencies=protected)
    app.include_router(projects.router, prefix=prefix, dependencies=protected)
    app.include_router(reports.router, prefix=prefix, dependencies=protected)
    app.include_router(schemas.router, prefix=prefix, dependencies=protected)
    app.include_router(users.router, prefix=prefix)  # require_admin at router level
    return app


async def _unknown_schema_handler(request: Request, exc: UnknownSchemaError) -> JSONResponse:
    """Actionable unknown-schema report: the payload is exactly what a
    schema-support issue needs (structure only, never row data)."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": str(exc),
            "platform": exc.platform,
            "user_version": exc.user_version,
            "tables": exc.tables,
            "how_to_contribute": (
                "This database uses a WhatsApp schema generation we don't have a "
                "query pack for yet. Please open a 'WhatsApp schema support' issue "
                "on GitHub including this JSON payload (it contains structure only)."
            ),
        },
    )


async def _unsupported_capability_handler(request: Request, exc: UnsupportedCapabilityError) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": str(exc)})


def _domain_error_handler(status_code: int):
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


app = create_app()
