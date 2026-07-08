"""Liveness/readiness probes and analyzer availability."""

from fastapi import APIRouter

from forensicwace_core import __version__
from forensicwace_core.analysis.analyzers import all_statuses

from ..schemas import AnalyzerStatusOut

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/readyz")
def readyz() -> dict:
    return {"status": "ready"}


@router.get("/api/v1/analyzers/status", response_model=list[AnalyzerStatusOut])
def analyzers_status():
    """Health check of every configured AI analyzer (may be slow: calls out)."""
    return [AnalyzerStatusOut(name=s.name, available=s.available, detail=str(s.detail)) for s in all_statuses()]
