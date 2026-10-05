"""Unit tests for PROTEUS SQLite storage layer."""

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

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
    MonitoringIntent,
    NormalizedContract,
    NormalizedOperation,
    NormalizedParameter,
    RawSnapshot,
    SourceDefinition,
    SourceType,
    StateNature,
)
from proteus.storage.database import Database


@pytest.fixture
def memory_db() -> Iterator[Database]:
    """Fixture providing an initialized in-memory database."""
    db = Database(":memory:")
    yield db
    db.close()


@pytest.fixture
def file_db() -> Iterator[Database]:
    """Fixture providing an initialized disk-backed temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tf:
        temp_path = tf.name
    db = Database(temp_path)
    yield db
    db.close()
    try:
        Path(temp_path).unlink(missing_ok=True)
    except Exception:
        pass


class TestDatabaseProjects:
    """Test project metadata storage operations."""

    def test_save_and_get_project(self, memory_db: Database) -> None:
        memory_db.save_project("proj-1", "Test Repo", "/repos/test")
        proj = memory_db.get_project("proj-1")
        assert proj is not None
        assert proj["id"] == "proj-1"
        assert proj["name"] == "Test Repo"
        assert proj["repository_path"] == "/repos/test"

    def test_list_projects(self, memory_db: Database) -> None:
        memory_db.save_project("p1", "Repo 1", "/repos/1")
        memory_db.save_project("p2", "Repo 2", "/repos/2")
        projects = memory_db.list_projects()
        assert len(projects) == 2


class TestDatabaseInventory:
    """Test ApiInventory hierarchy persistence."""

    def test_save_and_get_inventory(self, memory_db: Database) -> None:
        usage1 = ApiUsage(
            operation="generate_content",
            file="src/chat.py",
            line=10,
            symbol="client.models.generate_content",
            evidence_type=EvidenceType.AST_CALL,
            confidence=ConfidenceLevel.STRONG,
            context_snippet="res = client.models.generate_content(...)",
        )
        dep = ApiDependency(
            provider="google_gemini",
            base_url="https://generativelanguage.googleapis.com",
            sdk="google-genai",
            confidence=ConfidenceLevel.STRONG,
            usages=[usage1],
        )
        inv = ApiInventory(
            project_path="/repos/sample",
            dependencies=[dep],
        )

        memory_db.save_inventory("proj-sample", inv)
        retrieved = memory_db.get_inventory("proj-sample")
        assert retrieved is not None
        assert retrieved.total_dependencies == 1
        assert retrieved.dependencies[0].provider == "google_gemini"
        assert len(retrieved.dependencies[0].usages) == 1
        assert retrieved.dependencies[0].usages[0].line == 10
        assert retrieved.dependencies[0].usages[0].symbol == "client.models.generate_content"


class TestDatabaseIntent:
    """Test MonitoringIntent persistence."""

    def test_save_and_get_intent(self, memory_db: Database) -> None:
        intent = MonitoringIntent(
            intent_id="intent-1",
            provider="stripe",
            purpose="card_charges",
            relevant_capabilities=["charges"],
            target_resources=["payment_intents"],
            relevant_properties=["amount", "currency"],
            evidence=["src/billing.py:15"],
            status=IntentStatus.CONFIRMED,
        )
        memory_db.save_intent(intent, project_id=None)
        loaded = memory_db.get_intent("intent-1")
        assert loaded is not None
        assert loaded.provider == "stripe"
        assert loaded.relevant_capabilities == ["charges"]
        assert loaded.status == IntentStatus.CONFIRMED

    def test_list_intents_filtering(self, memory_db: Database) -> None:
        i1 = MonitoringIntent(intent_id="i1", provider="stripe", purpose="p1")
        i2 = MonitoringIntent(intent_id="i2", provider="gemini", purpose="p2")
        memory_db.save_intent(i1)
        memory_db.save_intent(i2)
        assert len(memory_db.list_intents()) == 2
        assert len(memory_db.list_intents(provider="stripe")) == 1


class TestDatabaseSources:
    """Test SourceDefinition persistence."""

    def test_save_and_get_source(self, memory_db: Database) -> None:
        src = SourceDefinition(
            source_id="src-stripe-spec",
            provider="stripe",
            source_type=SourceType.OPENAPI_SPEC,
            location="https://api.stripe.com/spec.json",
            authority=AuthorityClass.OFFICIAL_SPEC,
            collection_method=CollectionMethod.HTTP_GET,
            is_verified=True,
        )
        memory_db.save_source(src)
        loaded = memory_db.get_source("src-stripe-spec")
        assert loaded is not None
        assert loaded.provider == "stripe"
        assert loaded.is_verified is True
        assert loaded.authority == AuthorityClass.OFFICIAL_SPEC


class TestDatabaseSnapshots:
    """Test RawSnapshot persistence and immutability constraint."""

    def test_save_and_get_snapshot(self, memory_db: Database) -> None:
        snap = RawSnapshot.create_from_content(
            source_id="src-test",
            raw_content='{"models": ["gemini-1.5-flash"]}',
            status_code=200,
        )
        memory_db.save_snapshot(snap)
        loaded = memory_db.get_snapshot(snap.snapshot_id)
        assert loaded is not None
        assert loaded.raw_content == '{"models": ["gemini-1.5-flash"]}'
        assert loaded.content_hash == snap.content_hash
        assert loaded.fetch_status == FetchStatus.SUCCESS

    def test_snapshot_immutability(self, memory_db: Database) -> None:
        """Verify that overwriting an existing snapshot fails."""
        snap = RawSnapshot.create_from_content(
            source_id="src-immutable",
            raw_content="first version",
        )
        memory_db.save_snapshot(snap)

        # Attempt to insert identical snapshot_id with altered content
        snap_tampered = RawSnapshot(
            snapshot_id=snap.snapshot_id,
            source_id=snap.source_id,
            retrieved_at=snap.retrieved_at,
            content_hash="tampered_hash",
            raw_content="tampered content",
        )
        with pytest.raises(ValueError, match="already exists. Snapshots are immutable"):
            memory_db.save_snapshot(snap_tampered)


class TestDatabaseContractsAndChanges:
    """Test NormalizedContract and ChangeEvent persistence."""

    def test_save_and_get_contract(self, memory_db: Database) -> None:
        snap = RawSnapshot.create_from_content(
            source_id="src-c",
            raw_content="dummy",
        )
        memory_db.save_snapshot(snap)

        contract = NormalizedContract(
            contract_id="contract-1",
            snapshot_id=snap.snapshot_id,
            provider="stripe",
            state_nature=StateNature.DECLARED,
            endpoints=[
                NormalizedOperation(
                    path="/v1/charges",
                    method="POST",
                    parameters=[NormalizedParameter(name="amount", required=True)],
                )
            ],
        )
        memory_db.save_contract(contract)

        loaded = memory_db.get_contract("contract-1")
        assert loaded is not None
        assert loaded.provider == "stripe"
        assert len(loaded.endpoints) == 1
        assert loaded.endpoints[0].parameters[0].name == "amount"

    def test_save_and_get_change(self, memory_db: Database) -> None:
        snap1 = RawSnapshot.create_from_content(source_id="src-c", raw_content="v1")
        snap2 = RawSnapshot.create_from_content(source_id="src-c", raw_content="v2")
        memory_db.save_snapshot(snap1)
        memory_db.save_snapshot(snap2)

        change = ChangeEvent(
            change_id="chg-1",
            old_snapshot_id=snap1.snapshot_id,
            new_snapshot_id=snap2.snapshot_id,
            provider="stripe",
            target="POST /v1/charges (currency)",
            change_category=ChangeCategory.PARAMETER,
            change_type="parameter_required",
            severity=ChangeSeverity.BREAKING,
            old_state={"required": False},
            new_state={"required": True},
            evidence_references=["snapshot:snap1", "snapshot:snap2"],
        )
        memory_db.save_change(change)

        loaded = memory_db.get_change("chg-1")
        assert loaded is not None
        assert loaded.severity == ChangeSeverity.BREAKING
        assert loaded.old_state == {"required": False}
        assert loaded.new_state == {"required": True}
        assert len(memory_db.list_changes(provider="stripe")) == 1


class TestDatabaseDiskPersistence:
    """Test disk-backed SQLite database persistence across instances."""

    def test_persistence_across_connections(self, file_db: Database) -> None:
        db_path = file_db.db_path
        file_db.save_project("disk-proj", "Disk Project", "/disk/repo")

        # Open secondary connection to same file
        db2 = Database(db_path)
        proj = db2.get_project("disk-proj")
        assert proj is not None
        assert proj["name"] == "Disk Project"
        db2.close()
