"""Marketplace endpoints (phase B): browse the signed catalog, install from it.

Browsing is available to every operator; installing, like every registry
write, is admin-only. Installing a ``trust=cloud`` analyzer requires explicit
consent in the request — evidence content leaves the deployment — and the
consent is recorded on the audit trail.

Without a runtime provisioner (FW_PROVISIONER, phase C) installation is
bring-your-own-runtime: the operator starts the pinned container image and
passes its endpoint; the catalog still supplies identity, digest and trust.
"""

import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from forensicwace_core.analysis import registry
from forensicwace_core.analysis.analyzers import http_analyzer
from forensicwace_core.config import get_settings
from forensicwace_core.resultsdb.engine import session_scope
from forensicwace_core.resultsdb.models import Analyzer

from .. import audit, catalog
from ..auth import AuthUser, require_admin
from ..schemas import CatalogEntryOut, CatalogOut, InstalledAnalyzerOut, MarketplaceInstall
from .analyzers import _to_out

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


def _provisioner_enabled() -> bool:
    return bool(get_settings().provisioner)


def _to_entry_out(entry: catalog.CatalogEntry, installed: dict) -> CatalogEntryOut:
    manifest = entry.manifest
    row = installed.get(manifest.key)
    return CatalogEntryOut(
        key=manifest.key,
        name=manifest.name,
        version=manifest.version,
        capabilities=list(manifest.capabilities),
        input=manifest.input,
        trust=manifest.trust,
        gpu=manifest.resources.gpu,
        config_schema=manifest.config_schema,
        image=entry.image,
        image_digest=entry.image_digest,
        port=entry.port,
        description=entry.description,
        publisher=entry.publisher,
        homepage=entry.homepage,
        installed=row is not None,
        installed_version=row.version if row is not None else None,
    )


@router.get("", response_model=CatalogOut)
def browse_catalog():
    """The catalog with per-entry install state (any authenticated operator)."""
    try:
        loaded = catalog.load_catalog()
    except catalog.CatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    installed = registry.installed_analyzers()
    return CatalogOut(
        name=loaded.catalog.name,
        verified=loaded.verified,
        provisioner=_provisioner_enabled(),
        entries=[_to_entry_out(e, installed) for e in loaded.catalog.entries],
    )


@router.post("/install/{key}", response_model=InstalledAnalyzerOut, status_code=201)
def install_from_catalog(key: str, request: MarketplaceInstall, admin: AuthUser = Depends(require_admin)):
    try:
        entry = catalog.entry_for(key)
    except catalog.CatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if entry is None:
        raise HTTPException(status_code=404, detail=f"{key!r} is not in the catalog")
    if key in registry.BUILTINS:
        raise HTTPException(status_code=409, detail=f"{key!r} is a builtin analyzer key")

    if entry.manifest.trust == "cloud" and not request.consent:
        raise HTTPException(status_code=422, detail=_consent_required(key))

    with session_scope() as session:
        if session.query(Analyzer).filter_by(key=key).first() is not None:
            raise HTTPException(status_code=409, detail=f"Analyzer {key!r} is already installed")

    provisioned = False
    if _provisioner_enabled():
        try:
            from .. import provisioner
        except ImportError:
            raise HTTPException(status_code=503, detail="FW_PROVISIONER is set but no provisioner is available")
        try:
            endpoint = provisioner.provision(entry, config=request.config)
        except provisioner.ProvisionerError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        provisioned = True
    elif request.endpoint:
        endpoint = request.endpoint.rstrip("/")
    else:
        raise HTTPException(
            status_code=422,
            detail=(
                "No runtime provisioner is configured (FW_PROVISIONER): start the pinned "
                f"image {entry.image} yourself and pass its endpoint"
            ),
        )

    # the running container must be what the catalog says it is
    try:
        live = http_analyzer.HttpAnalyzer(endpoint).manifest()
    except (httpx.HTTPError, OSError) as exc:
        _rollback_provisioned(key, provisioned)
        raise HTTPException(status_code=502, detail=f"Cannot fetch {endpoint}/manifest: {exc}")
    except ValidationError as exc:
        _rollback_provisioned(key, provisioned)
        raise HTTPException(status_code=422, detail=f"Manifest does not conform to fw-analyzer/1: {exc}")
    except ValueError:
        _rollback_provisioned(key, provisioned)
        raise HTTPException(status_code=422, detail=f"{endpoint}/manifest did not return valid JSON")
    if live.key != key:
        _rollback_provisioned(key, provisioned)
        raise HTTPException(
            status_code=422,
            detail=f"The container at {endpoint} serves analyzer {live.key!r}, not {key!r}",
        )

    # Never soften the catalog's trust statement with the container's own —
    # and if the live manifest ESCALATES to cloud, the consent gate applies to
    # that too: the catalog said local, so the operator was never asked.
    trust = "cloud" if "cloud" in (entry.manifest.trust, live.trust) else "local"
    if trust == "cloud" and not request.consent:
        _rollback_provisioned(key, provisioned)
        raise HTTPException(status_code=422, detail=_consent_required(key))

    now = datetime.now(timezone.utc)
    try:
        with session_scope() as session:
            row = Analyzer(
                key=key,
                name=entry.manifest.name,
                version=live.version,
                type="http",
                capabilities=list(entry.manifest.capabilities),
                input=entry.manifest.input,
                trust=trust,
                endpoint=endpoint,
                # Chain of custody: the pinned image is recorded only when the
                # provisioner deployed it. A bring-your-own endpoint is running
                # unverified software — stamping the catalog digest on its
                # findings would claim a provenance nobody checked.
                image=entry.image if provisioned else None,
                image_digest=entry.image_digest if provisioned else None,
                config=request.config,
                enabled=True,
                installed_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            out = _to_out(registry.resolved_from_row(row))
    except IntegrityError:
        # concurrent install of the same key won the race
        _rollback_provisioned(key, provisioned)
        raise HTTPException(status_code=409, detail=f"Analyzer {key!r} is already installed")
    registry.clear_registry_cache()

    if trust == "cloud":  # the gate above guarantees consent was given
        audit.record(admin, "analyzer.consent", resource=key, detail="trust=cloud: evidence egress approved")
    audit.record(
        admin, "analyzer.installed", resource=key,
        detail=f"image={entry.image} version={live.version} trust={trust} endpoint={endpoint} provisioned={provisioned}",
    )
    return out


def _consent_required(key: str) -> str:
    return (
        f"{key!r} is a trust=cloud analyzer: evidence content will be sent to an "
        "external service. Installing it requires explicit consent (consent=true)."
    )


def _rollback_provisioned(key: str, provisioned: bool) -> None:
    """Tear the runtime down again when an install fails halfway."""
    if not provisioned:
        return
    try:
        from .. import provisioner

        provisioner.deprovision(key)
    except Exception:
        logger.warning("Could not roll back provisioned runtime for %s", key, exc_info=True)
