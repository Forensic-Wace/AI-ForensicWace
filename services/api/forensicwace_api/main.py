"""Forensic Wace REST API.

Stateless by design: every request carries the backup it refers to; there is
no per-client server-side session. OpenAPI docs are served at ``/docs``.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from forensicwace_core.config import get_settings
from forensicwace_core.exceptions import (
    BackupNotFoundError,
    ConfigurationError,
    ExtractionError,
    InvalidIdentifierError,
)

from .routers import analyses, backups, chats_android, chats_ios, health, reports

logger = logging.getLogger(__name__)

_ERROR_STATUS = {
    InvalidIdentifierError: 400,
    BackupNotFoundError: 404,
    ExtractionError: 422,
    ConfigurationError: 503,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().database_url:
        from forensicwace_core.resultsdb.engine import init_db

        try:
            init_db()
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tightened when auth lands (Phase 2)
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for exc_type, status_code in _ERROR_STATUS.items():
        app.add_exception_handler(exc_type, _domain_error_handler(status_code))

    app.include_router(health.router)
    prefix = "/api/v1"
    app.include_router(backups.router, prefix=prefix)
    app.include_router(chats_ios.router, prefix=prefix)
    app.include_router(chats_android.router, prefix=prefix)
    app.include_router(analyses.router, prefix=prefix)
    app.include_router(reports.router, prefix=prefix)
    return app


def _domain_error_handler(status_code: int):
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


app = create_app()
