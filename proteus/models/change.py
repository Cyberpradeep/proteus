"""Detected API evolution and semantic change event data models."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ChangeCategory(StrEnum):
    """Category of API change detected between snapshots."""

    ENDPOINT = "ENDPOINT"
    PARAMETER = "PARAMETER"
    REQUEST_SCHEMA = "REQUEST_SCHEMA"
    RESPONSE_SCHEMA = "RESPONSE_SCHEMA"
    LIFECYCLE = "LIFECYCLE"
    DOCUMENTATION = "DOCUMENTATION"
    BEHAVIORAL_CANDIDATE = "BEHAVIORAL_CANDIDATE"
    UNKNOWN = "UNKNOWN"


class ChangeSeverity(StrEnum):
    """Impact severity classification of detected change.

    HLD Section 12:
    - BREAKING (Definite breaking change, e.g. required parameter added)
    - POTENTIALLY_BREAKING (Warning level compatibility risk)
    - NON_BREAKING (Informational evolution, e.g. optional parameter added)
    - UNKNOWN (Cannot safely determine without further evidence)
    """

    BREAKING = "BREAKING"
    POTENTIALLY_BREAKING = "POTENTIALLY_BREAKING"
    NON_BREAKING = "NON_BREAKING"
    UNKNOWN = "UNKNOWN"


class ChangeEvent(BaseModel):
    """Structured semantic difference between two normalized contract snapshots.

    Contract Section 11 & HLD Table 6:
    Must contain target, change type, old/new state, severity,
    evidence references, and detection timestamp.
    """

    change_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this change event",
    )
    old_snapshot_id: str | None = Field(
        default=None,
        description="Reference to prior RawSnapshot (None if newly introduced resource)",
    )
    new_snapshot_id: str = Field(
        description="Reference to current RawSnapshot where change was detected"
    )
    provider: str = Field(description="Target API provider identifier")
    target: str = Field(
        description="Target element altered (e.g. 'POST /payment_intents', 'param:currency')"
    )
    change_category: ChangeCategory = Field(description="Functional category of the change")
    change_type: str = Field(
        description="Specific change identifier (e.g. 'parameter_required', 'endpoint_removed')"
    )
    severity: ChangeSeverity = Field(description="Compatibility impact rating")
    old_state: dict[str, Any] | None = Field(
        default=None,
        description="Prior normalized state representation of target element",
    )
    new_state: dict[str, Any] | None = Field(
        default=None,
        description="Updated normalized state representation of target element",
    )
    evidence_references: list[str] = Field(
        default_factory=list,
        description="Audit references: snapshot hashes, spec paths, changelog citations",
    )
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when change was detected",
    )
