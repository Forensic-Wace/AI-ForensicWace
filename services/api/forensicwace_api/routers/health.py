"""Liveness/readiness probes.

Analyzer availability lives in the analyzers router (same URL as before:
``/api/v1/analyzers/status``), backed by the dynamic registry.
"""

from fastapi import APIRouter

from forensicwace_core import __version__

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/readyz")
def readyz() -> dict:
    return {"status": "ready"}
