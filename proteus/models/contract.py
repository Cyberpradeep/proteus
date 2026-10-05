"""Normalized provider-neutral API contract data models."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StateNature(StrEnum):
    """Origin nature of normalized API state.

    HLD Section 11:
    Distinguishes provider-declared contracts from observed runtime telemetry.
    """

    DECLARED = "DECLARED"
    OBSERVED = "OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"
    UNKNOWN = "UNKNOWN"


class LifecycleStatus(StrEnum):
    """Lifecycle status of an operation, parameter, or model."""

    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    SUNSET = "SUNSET"
    UNKNOWN = "UNKNOWN"


class NormalizedParameter(BaseModel):
    """Canonical representation of an operation parameter."""

    name: str = Field(description="Parameter name")
    in_location: str = Field(
        default="query",
        description="Location: 'query', 'header', 'path', 'cookie', or 'body'",
    )
    required: bool = Field(default=False, description="Whether parameter is mandatory")
    param_type: str = Field(default="string", description="Primitive or complex schema type")
    description: str | None = Field(default=None, description="Parameter description")
    enum_values: list[str] | None = Field(
        default=None, description="Allowed enum values if constrained"
    )
    default_value: Any = Field(default=None, description="Default value if omitted")


class NormalizedOperation(BaseModel):
    """Canonical representation of an API operation / endpoint."""

    operation_id: str | None = Field(default=None, description="Unique operation identifier")
    path: str = Field(description="URL route path (e.g. '/v1/chat/completions')")
    method: str = Field(description="HTTP method (e.g. 'GET', 'POST', 'DELETE')")
    summary: str | None = Field(default=None, description="Short summary of operation")
    parameters: list[NormalizedParameter] = Field(
        default_factory=list, description="Canonical operation parameters"
    )
    request_schema: dict[str, Any] | None = Field(
        default=None, description="Canonical JSON Schema of request payload"
    )
    response_schema: dict[str, Any] | None = Field(
        default=None, description="Canonical JSON Schema of primary response payload"
    )
    lifecycle_status: LifecycleStatus = Field(
        default=LifecycleStatus.ACTIVE, description="Lifecycle status"
    )


class NormalizedContract(BaseModel):
    """Provider-neutral canonical representation of an API's surface and state.

    Contract Section 11:
    Normalize provider data first, then compare normalized state.
    """

    contract_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this normalized contract",
    )
    snapshot_id: str = Field(description="Foreign key reference to underlying RawSnapshot")
    provider: str = Field(description="API provider identifier")
    schema_version: str = Field(default="1.0", description="Contract normalization schema version")
    state_nature: StateNature = Field(
        default=StateNature.DECLARED,
        description="Whether this represents declared contract or observed runtime state",
    )
    endpoints: list[NormalizedOperation] = Field(
        default_factory=list, description="List of normalized operations and endpoints"
    )
    models_or_resources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of available models or resources (e.g. LLM model catalog)",
    )
    lifecycle_entries: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Deprecations, sunset dates, and lifecycle announcements",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional normalizer metadata"
    )
    normalized_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when normalization was performed",
    )
