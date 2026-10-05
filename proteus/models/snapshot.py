"""Raw snapshot persistence and evidence data models."""

import hashlib
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class FetchStatus(StrEnum):
    """Outcome status of raw evidence collection."""

    SUCCESS = "SUCCESS"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    PARSE_ERROR = "PARSE_ERROR"
    UNKNOWN = "UNKNOWN"


def compute_sha256(content: str) -> str:
    """Compute deterministic SHA-256 hex digest of string content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class RawSnapshot(BaseModel):
    """Immutable, timestamped historical capture of an authoritative source.

    Contract Section 10:
    Never keep only the latest state. Store immutable or content-addressed
    historical snapshots with metadata:
    source_id, retrieved_at, content_hash, status_code, etag, last_modified, raw_content.
    """

    snapshot_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this snapshot",
    )
    source_id: str = Field(description="Foreign key reference to SourceDefinition")
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Exact timestamp when content was retrieved",
    )
    content_hash: str = Field(description="SHA-256 hash of raw_content for cryptographic integrity")
    status_code: int | None = Field(
        default=None,
        description="HTTP response status code if acquired via HTTP",
    )
    etag: str | None = Field(
        default=None,
        description="HTTP ETag header for conditional revalidation",
    )
    last_modified: str | None = Field(
        default=None,
        description="HTTP Last-Modified header for conditional revalidation",
    )
    content_type: str | None = Field(
        default=None,
        description="MIME type of retrieved content (e.g. 'application/json')",
    )
    raw_content: str = Field(description="Exact raw text/JSON/YAML payload retrieved from source")
    fetch_status: FetchStatus = Field(
        default=FetchStatus.SUCCESS,
        description="Fetch outcome status",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if fetch or parsing encountered an issue",
    )

    @classmethod
    def create_from_content(
        cls,
        source_id: str,
        raw_content: str,
        status_code: int | None = 200,
        etag: str | None = None,
        last_modified: str | None = None,
        content_type: str | None = "application/json",
        fetch_status: FetchStatus = FetchStatus.SUCCESS,
        error_message: str | None = None,
    ) -> "RawSnapshot":
        """Factory method computing content_hash automatically."""
        return cls(
            source_id=source_id,
            content_hash=compute_sha256(raw_content),
            status_code=status_code,
            etag=etag,
            last_modified=last_modified,
            content_type=content_type,
            raw_content=raw_content,
            fetch_status=fetch_status,
            error_message=error_message,
        )
