"""Authoritative provider source definition and registry data models."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    """Classification of external evidence source."""

    LIVE_RESOURCE = "LIVE_RESOURCE"
    OPENAPI_SPEC = "OPENAPI_SPEC"
    CHANGELOG = "CHANGELOG"
    DEPRECATION_DOC = "DEPRECATION_DOC"
    SDK_REGISTRY = "SDK_REGISTRY"
    RUNTIME_TELEMETRY = "RUNTIME_TELEMETRY"
    UNKNOWN = "UNKNOWN"


class AuthorityClass(StrEnum):
    """Authority ranking and verification class of the source."""

    OFFICIAL_ENDPOINT = "OFFICIAL_ENDPOINT"
    OFFICIAL_SPEC = "OFFICIAL_SPEC"
    OFFICIAL_CHANGELOG = "OFFICIAL_CHANGELOG"
    OFFICIAL_DOCS = "OFFICIAL_DOCS"
    SDK_METADATA = "SDK_METADATA"
    VERIFIED_THIRD_PARTY = "VERIFIED_THIRD_PARTY"
    CANDIDATE_UNVERIFIED = "CANDIDATE_UNVERIFIED"
    UNTRUSTED = "UNTRUSTED"


class CollectionMethod(StrEnum):
    """Mechanism for collecting state from this source."""

    HTTP_GET = "HTTP_GET"
    HTTP_POLL = "HTTP_POLL"
    WEBHOOK = "WEBHOOK"
    REGISTRY_META = "REGISTRY_META"
    TELEMETRY_EVENT = "TELEMETRY_EVENT"


class SourceDefinition(BaseModel):
    """Authoritative source configuration for monitoring an API capability.

    Contract Section 8:
    Every source must be verified against domain identity, scheme, and authority
    before promoting into the trusted Source Registry.
    """

    source_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier or slug for this source definition",
    )
    provider: str = Field(description="Target API provider identifier")
    source_type: SourceType = Field(description="Type of source being monitored")
    location: str = Field(description="Source location: HTTPS URL, endpoint, or relative file path")
    purpose: str | None = Field(
        default=None,
        description="Capability or intent aspect this source informs",
    )
    authority: AuthorityClass = Field(
        default=AuthorityClass.CANDIDATE_UNVERIFIED,
        description="Authority tier of the source",
    )
    collection_method: CollectionMethod = Field(
        default=CollectionMethod.HTTP_GET,
        description="How data is retrieved from this source",
    )
    freshness_policy: str | None = Field(
        default="6h",
        description="Polling cadence or TTL (e.g. '6h', '1d')",
    )
    is_verified: bool = Field(
        default=False,
        description="Whether this source passed deterministic authority verification",
    )
    validation_notes: str | None = Field(
        default=None,
        description="Details on verification outcome or SSRF validation checks",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when source was registered",
    )
