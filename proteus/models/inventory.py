"""API Discovery and repository consumer inventory data models."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceType(StrEnum):
    """Source of discovery evidence."""

    MANIFEST = "MANIFEST"
    SDK_IMPORT = "SDK_IMPORT"
    AST_CALL = "AST_CALL"
    HTTP_CALL = "HTTP_CALL"
    CONFIG = "CONFIG"
    RUNTIME_TRACE = "RUNTIME_TRACE"
    UNKNOWN = "UNKNOWN"


class ConfidenceLevel(StrEnum):
    """Confidence level of discovered API dependency or usage."""

    CANDIDATE = "CANDIDATE"
    STRONG = "STRONG"
    CONFIRMED = "CONFIRMED"
    UNKNOWN = "UNKNOWN"


class ApiUsage(BaseModel):
    """Specific location and character of API usage in consumer code."""

    operation: str | None = Field(default=None, description="Operation or method name invoked")
    method: str | None = Field(default=None, description="HTTP method e.g. GET, POST if known")
    path: str | None = Field(default=None, description="Endpoint path or symbol path")
    file: str = Field(description="Relative path of file in consumer repository")
    line: int = Field(ge=1, description="1-indexed line number of usage site")
    end_line: int | None = Field(
        default=None, ge=1, description="Ending line number if range known"
    )
    symbol: str | None = Field(default=None, description="Exact symbol or AST node identifier")
    evidence_type: EvidenceType = Field(
        default=EvidenceType.AST_CALL, description="Type of evidence confirming this usage"
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.STRONG, description="Confidence in this call site"
    )
    context_snippet: str | None = Field(
        default=None, description="Bounded source code context around usage"
    )


class ApiDependency(BaseModel):
    """External API dependency identified within consumer repository."""

    provider: str = Field(
        description="Provider identifier (e.g. 'google_gemini', 'stripe', 'github')"
    )
    base_url: str | None = Field(default=None, description="Discovered base URL or host")
    sdk: str | None = Field(
        default=None, description="SDK package name if manifest/import evidence"
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.CANDIDATE, description="Aggregate dependency confidence"
    )
    usages: list[ApiUsage] = Field(
        default_factory=list, description="Specific observed call sites in the repository"
    )


class ApiInventory(BaseModel):
    """Complete inventory of discovered external API dependencies for a repository."""

    project_path: str = Field(description="Root path or identifier of scanned repository")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when inventory was generated",
    )
    dependencies: list[ApiDependency] = Field(
        default_factory=list, description="List of discovered provider dependencies"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional discovery metadata or scanner versions"
    )

    @property
    def total_dependencies(self) -> int:
        return len(self.dependencies)

    @property
    def total_usages(self) -> int:
        return sum(len(dep.usages) for dep in self.dependencies)
