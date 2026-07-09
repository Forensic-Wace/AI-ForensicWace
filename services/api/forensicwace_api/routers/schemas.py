"""WhatsApp schema registry endpoints."""

from fastapi import APIRouter

from forensicwace_core.schema_registry import list_descriptors

router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.get("")
def supported_schemas() -> list[dict]:
    """Every schema generation the platform can analyze, with its capabilities."""
    return [
        {
            "id": d.id,
            "platform": d.platform,
            "display_name": d.display_name,
            "priority": d.priority,
            "queries": {name: file is not None for name, file in d.queries.items()},
            "capabilities": d.capabilities,
        }
        for d in list_descriptors()
    ]
