"""The fw-analyzer/1 contract: models shared by the platform and analyzers.

Any container exposing ``GET /manifest``, ``GET /healthz`` and
``POST /analyze`` with these payloads is installable at runtime. The JSON
Schemas in ``schemas/analyzer/`` are generated from these models (kept in
sync by a test); the human spec is ``docs/analyzer-contract.md``.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

CONTRACT_VERSION = "fw-analyzer/1"

Capability = Literal["pii", "password", "transcription", "ocr", "caption"]
InputType = Literal["text", "audio", "image"]
Trust = Literal["local", "cloud"]

TEXT_CAPABILITIES: frozenset[str] = frozenset({"pii", "password"})
MEDIA_CAPABILITIES: frozenset[str] = frozenset({"transcription", "ocr", "caption"})

# Which input type each capability operates on.
CAPABILITY_INPUT: dict[str, str] = {
    "pii": "text",
    "password": "text",
    "transcription": "audio",
    "ocr": "image",
    "caption": "image",
}


class AnalyzerResources(BaseModel):
    """Scheduling hints used by the phase-C provisioner; advisory in phase A."""

    cpu: Optional[str] = None
    memory: Optional[str] = None
    gpu: bool = False


class AnalyzerManifest(BaseModel):
    contract: Literal["fw-analyzer/1"]
    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$", description="Stable unique id, referenced by analysis requests")
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=50)
    capabilities: list[Capability] = Field(min_length=1)
    input: InputType
    config_schema: dict = Field(default_factory=dict, description="JSON Schema of the operator-facing options")
    resources: AnalyzerResources = AnalyzerResources()
    trust: Trust = Field(default="local", description="local = evidence never leaves the deployment")

    @model_validator(mode="after")
    def _capabilities_match_input(self) -> "AnalyzerManifest":
        for capability in self.capabilities:
            if CAPABILITY_INPUT[capability] != self.input:
                raise ValueError(f"capability {capability!r} requires input {CAPABILITY_INPUT[capability]!r}, not {self.input!r}")
        return self


class ContractFinding(BaseModel):
    kind: Literal["pii", "password"]
    value: str
    entity_type: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class Enrichment(BaseModel):
    transcription: Optional[str] = None
    ocr_text: Optional[str] = None
    caption: Optional[str] = None


class AnalyzeResponse(BaseModel):
    """Text analyzers return findings; media analyzers return enrichment."""

    findings: list[ContractFinding] = []
    enrichment: Optional[Enrichment] = None
