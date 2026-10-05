"""Consumer intent profiling data models."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class IntentStatus(StrEnum):
    """Validation status of inferred intent profile."""

    CONFIRMED = "CONFIRMED"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"
    CANNOT_SAFELY_DETERMINE = "CANNOT_SAFELY_DETERMINE"


class MonitoringIntent(BaseModel):
    """Structured representation of why an API is used and what capabilities matter.

    Contract Section 7:
    The output is a hypothesis/profile to be verified, not live truth.
    Input must be bounded repository context, not entire repo.
    """

    intent_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this intent profile",
    )
    provider: str = Field(description="Target API provider identifier")
    purpose: str = Field(
        description="Inferred high-level application purpose (e.g. 'text_generation')"
    )
    relevant_capabilities: list[str] = Field(
        default_factory=list,
        description="Specific provider capabilities relevant to application",
    )
    target_resources: list[str] = Field(
        default_factory=list,
        description="Specific models, endpoints, or resources targeted",
    )
    relevant_properties: list[str] = Field(
        default_factory=list,
        description="Specific request/response properties of interest",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Repository file:line citations supporting this intent profile",
    )
    status: IntentStatus = Field(
        default=IntentStatus.CONFIRMED,
        description="Explicit certainty state of this profile",
    )
    notes: str | None = Field(
        default=None,
        description="Additional context or ambiguity notes",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when intent profile was synthesized",
    )
