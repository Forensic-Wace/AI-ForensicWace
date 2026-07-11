"""Analyzer registry endpoints (marketplace phase A).

``GET /analyzers`` lists the installed analyzers (dynamic: drives the UI
checkboxes); ``POST`` registers a running fw-analyzer/1 container by
endpoint (bring-your-own-container — catalog-driven install is phase B);
``PATCH``/``DELETE`` manage operator state. ``GET /analyzers/status`` is the
live health check (moved here from the health router, same URL).
"""

import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from forensicwace_core.analysis import registry
from forensicwace_core.analysis.analyzers import http_analyzer
from forensicwace_core.resultsdb.engine import session_scope
from forensicwace_core.resultsdb.models import Analyzer

from ..auth import require_admin
from ..schemas import AnalyzerRegister, AnalyzerStatusOut, AnalyzerUpdate, InstalledAnalyzerOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyzers", tags=["analyzers"])


def _to_out(analyzer: registry.ResolvedAnalyzer) -> InstalledAnalyzerOut:
    return InstalledAnalyzerOut(
        key=analyzer.key,
        name=analyzer.name,
        version=analyzer.version,
        type=analyzer.type,
        capabilities=list(analyzer.capabilities),
        input=analyzer.input,
        trust=analyzer.trust,
        enabled=analyzer.enabled,
        endpoint=analyzer.endpoint,
        image_digest=analyzer.image_digest,
        config=analyzer.config or {},
    )


@router.get("", response_model=list[InstalledAnalyzerOut])
def list_analyzers():
    """Installed analyzers (falls back to the built-ins when no database)."""
    installed = registry.installed_analyzers().values()
    return [_to_out(a) for a in sorted(installed, key=lambda a: (a.input != "text", a.key))]


@router.get("/status", response_model=list[AnalyzerStatusOut])
def analyzers_status():
    """Live health check of every installed analyzer (may be slow: calls out)."""
    return [AnalyzerStatusOut(name=s.name, available=s.available, detail=str(s.detail)) for s in registry.all_statuses()]


@router.post("", response_model=InstalledAnalyzerOut, status_code=201, dependencies=[Depends(require_admin)])
def register_analyzer(request: AnalyzerRegister):
    """Register a running fw-analyzer/1 container; its manifest is authoritative."""
    try:
        manifest = http_analyzer.HttpAnalyzer(request.endpoint).manifest()
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(status_code=502, detail=f"Cannot fetch {request.endpoint}/manifest: {exc}")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Manifest does not conform to fw-analyzer/1: {exc}")

    if manifest.key in registry.BUILTINS:
        raise HTTPException(status_code=409, detail=f"{manifest.key!r} is a builtin analyzer key")

    now = datetime.now(timezone.utc)
    with session_scope() as session:
        if session.query(Analyzer).filter_by(key=manifest.key).first() is not None:
            raise HTTPException(status_code=409, detail=f"Analyzer {manifest.key!r} is already installed")
        row = Analyzer(
            key=manifest.key,
            name=manifest.name,
            version=manifest.version,
            type="http",
            capabilities=list(manifest.capabilities),
            input=manifest.input,
            trust=manifest.trust,
            endpoint=request.endpoint.rstrip("/"),
            config=request.config,
            enabled=request.enabled,
            installed_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        out = _to_out(registry.resolved_from_row(row))
    registry.clear_registry_cache()
    return out


@router.patch("/{key}", response_model=InstalledAnalyzerOut, dependencies=[Depends(require_admin)])
def update_analyzer(key: str, request: AnalyzerUpdate):
    with session_scope() as session:
        row = session.query(Analyzer).filter_by(key=key).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Analyzer not installed")
        if request.enabled is not None:
            row.enabled = request.enabled
        if request.config is not None:
            row.config = request.config
        row.updated_at = datetime.now(timezone.utc)
        session.flush()
        out = _to_out(registry.resolved_from_row(row))
    registry.clear_registry_cache()
    return out


@router.delete("/{key}", status_code=204, dependencies=[Depends(require_admin)])
def uninstall_analyzer(key: str):
    """Remove a runtime-installed analyzer. Built-ins can only be disabled."""
    with session_scope() as session:
        row = session.query(Analyzer).filter_by(key=key).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Analyzer not installed")
        if row.type == "builtin":
            raise HTTPException(status_code=409, detail="Built-in analyzers cannot be uninstalled — disable instead")
        session.delete(row)
    registry.clear_registry_cache()
