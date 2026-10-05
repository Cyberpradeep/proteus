"""Unit tests for PROTEUS core Pydantic artifact models."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from proteus.models import (
    ApiDependency,
    ApiInventory,
    ApiUsage,
    AuthorityClass,
    ChangeCategory,
    ChangeEvent,
    ChangeSeverity,
    CollectionMethod,
    ConfidenceLevel,
    EvidenceType,
    FetchStatus,
    IntentStatus,
    LifecycleStatus,
    MonitoringIntent,
    NormalizedContract,
    NormalizedOperation,
    NormalizedParameter,
    RawSnapshot,
    SourceDefinition,
    SourceType,
    StateNature,
    UncertaintyState,
    compute_sha256,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "contracts"


class TestUncertainty:
    """Test explicit uncertainty representation."""

    def test_uncertainty_states_exist(self) -> None:
        assert UncertaintyState.UNKNOWN.value == "UNKNOWN"
        assert UncertaintyState.UNAVAILABLE.value == "UNAVAILABLE"
        assert UncertaintyState.AMBIGUOUS.value == "AMBIGUOUS"
        assert UncertaintyState.NOT_OBSERVED.value == "NOT_OBSERVED"
        assert UncertaintyState.CANNOT_SAFELY_DETERMINE.value == "CANNOT_SAFELY_DETERMINE"


class TestApiInventory:
    """Test ApiInventory model and nested dependencies/usages."""

    def test_inventory_creation(self) -> None:
        usage = ApiUsage(
            operation="generate_content",
            file="src/ai.py",
            line=42,
            symbol="client.models.generate_content",
            evidence_type=EvidenceType.AST_CALL,
            confidence=ConfidenceLevel.STRONG,
        )
        dep = ApiDependency(
            provider="google_gemini",
            base_url="https://generativelanguage.googleapis.com",
            sdk="google-genai",
            confidence=ConfidenceLevel.STRONG,
            usages=[usage],
        )
        inv = ApiInventory(
            project_path="/repos/test-app",
            dependencies=[dep],
        )
        assert inv.total_dependencies == 1
        assert inv.total_usages == 1
        assert inv.dependencies[0].provider == "google_gemini"

    def test_inventory_fixture_roundtrip(self) -> None:
        path = FIXTURES_DIR / "inventory.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        inv = ApiInventory.model_validate(data)
        assert inv.total_dependencies == 2
        assert inv.dependencies[0].provider == "google_gemini"
        assert inv.dependencies[1].provider == "stripe"
        assert inv.dependencies[1].usages[0].method == "POST"


class TestMonitoringIntent:
    """Test MonitoringIntent model."""

    def test_intent_creation(self) -> None:
        intent = MonitoringIntent(
            provider="stripe",
            purpose="card_payments",
            relevant_capabilities=["charges", "payment_intents"],
            status=IntentStatus.CONFIRMED,
        )
        assert intent.provider == "stripe"
        assert intent.status == IntentStatus.CONFIRMED

    def test_intent_uncertainty_state(self) -> None:
        intent = MonitoringIntent(
            provider="unknown_api",
            purpose="ambiguous_integration",
            status=IntentStatus.CANNOT_SAFELY_DETERMINE,
            notes="Dynamic string URL without AST confirmation",
        )
        assert intent.status == IntentStatus.CANNOT_SAFELY_DETERMINE

    def test_intent_fixture_roundtrip(self) -> None:
        path = FIXTURES_DIR / "intent.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        intent = MonitoringIntent.model_validate(data)
        assert intent.provider == "google_gemini"
        assert "model_availability" in intent.relevant_capabilities


class TestSourceDefinition:
    """Test SourceDefinition model."""

    def test_source_creation(self) -> None:
        src = SourceDefinition(
            source_id="src-gemini-live",
            provider="google_gemini",
            source_type=SourceType.LIVE_RESOURCE,
            location="https://generativelanguage.googleapis.com/v1beta/models",
            authority=AuthorityClass.OFFICIAL_ENDPOINT,
            collection_method=CollectionMethod.HTTP_GET,
            is_verified=True,
        )
        assert src.is_verified is True
        assert src.authority == AuthorityClass.OFFICIAL_ENDPOINT

    def test_source_fixture_roundtrip(self) -> None:
        path = FIXTURES_DIR / "source.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        src = SourceDefinition.model_validate(data)
        assert src.provider == "stripe"
        assert src.source_type == SourceType.OPENAPI_SPEC
        assert src.is_verified is True


class TestRawSnapshot:
    """Test RawSnapshot model and hashing."""

    def test_snapshot_creation_and_hash(self) -> None:
        content = '{"openapi": "3.0.0"}'
        expected_hash = compute_sha256(content)
        snap = RawSnapshot.create_from_content(
            source_id="src-1",
            raw_content=content,
            status_code=200,
            etag='"etag-123"',
        )
        assert snap.content_hash == expected_hash
        assert snap.fetch_status == FetchStatus.SUCCESS
        assert snap.etag == '"etag-123"'

    def test_snapshot_unavailable_state(self) -> None:
        snap = RawSnapshot(
            source_id="src-fail",
            retrieved_at=datetime.now(UTC),
            content_hash=compute_sha256(""),
            raw_content="",
            fetch_status=FetchStatus.UNAVAILABLE,
            error_message="HTTP 503 Service Unavailable",
        )
        assert snap.fetch_status == FetchStatus.UNAVAILABLE
        assert snap.error_message is not None

    def test_snapshot_fixture_roundtrip(self) -> None:
        path = FIXTURES_DIR / "snapshot.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        snap = RawSnapshot.model_validate(data)
        assert snap.status_code == 200
        assert snap.content_hash == compute_sha256(snap.raw_content)

    def test_snapshot_direct_construction_hash_validation(self) -> None:
        """Verify M-3: direct RawSnapshot construction with matching hash succeeds."""
        payload = "test payload"
        snap = RawSnapshot(
            source_id="src-1",
            content_hash=compute_sha256(payload),
            raw_content=payload,
        )
        assert snap.content_hash == compute_sha256(payload)

    def test_snapshot_direct_construction_mismatched_hash_fails(self) -> None:
        """Verify M-3: direct construction with mismatched hash raises ValidationError."""
        with pytest.raises(ValidationError, match="content_hash mismatch"):
            RawSnapshot(
                source_id="src-1",
                content_hash="invalid_hash_value",
                raw_content="test payload",
            )


class TestNormalizedContract:
    """Test NormalizedContract model."""

    def test_contract_creation(self) -> None:
        op = NormalizedOperation(
            operation_id="getModels",
            path="/v1/models",
            method="GET",
            parameters=[NormalizedParameter(name="pageSize", in_location="query", required=False)],
            lifecycle_status=LifecycleStatus.ACTIVE,
        )
        contract = NormalizedContract(
            snapshot_id="snap-1",
            provider="google_gemini",
            state_nature=StateNature.DECLARED,
            endpoints=[op],
        )
        assert len(contract.endpoints) == 1
        assert contract.endpoints[0].method == "GET"
        assert contract.state_nature == StateNature.DECLARED

    def test_contract_fixtures_roundtrip(self) -> None:
        v1_path = FIXTURES_DIR / "v1_contract.json"
        v1_data = json.loads(v1_path.read_text(encoding="utf-8"))
        c1 = NormalizedContract.model_validate(v1_data)
        assert c1.endpoints[0].parameters[1].required is False

        v2_path = FIXTURES_DIR / "v2_contract.json"
        v2_data = json.loads(v2_path.read_text(encoding="utf-8"))
        c2 = NormalizedContract.model_validate(v2_data)
        assert c2.endpoints[0].parameters[1].required is True
        assert len(c2.lifecycle_entries) == 1


class TestChangeEvent:
    """Test ChangeEvent model."""

    def test_change_event_creation(self) -> None:
        chg = ChangeEvent(
            new_snapshot_id="snap-2",
            provider="stripe",
            target="POST /v1/payment_intents (body.currency)",
            change_category=ChangeCategory.PARAMETER,
            change_type="parameter_required",
            severity=ChangeSeverity.BREAKING,
            old_state={"required": False},
            new_state={"required": True},
            evidence_references=["snapshot:snap-1", "snapshot:snap-2"],
        )
        assert chg.severity == ChangeSeverity.BREAKING
        assert chg.change_category == ChangeCategory.PARAMETER

    def test_change_fixture_roundtrip(self) -> None:
        path = FIXTURES_DIR / "change_event.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        chg = ChangeEvent.model_validate(data)
        assert chg.severity == ChangeSeverity.BREAKING
        assert chg.change_type == "parameter_required"
        assert len(chg.evidence_references) == 2
