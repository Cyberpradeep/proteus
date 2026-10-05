"""Relational SQLite storage manager for PROTEUS artifacts."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from proteus.models.change import ChangeCategory, ChangeEvent, ChangeSeverity
from proteus.models.contract import NormalizedContract
from proteus.models.intent import IntentStatus, MonitoringIntent
from proteus.models.inventory import (
    ApiDependency,
    ApiInventory,
    ApiUsage,
    ConfidenceLevel,
    EvidenceType,
)
from proteus.models.snapshot import FetchStatus, RawSnapshot
from proteus.models.source import (
    AuthorityClass,
    CollectionMethod,
    SourceDefinition,
    SourceType,
)
from proteus.storage.schema import SCHEMA_DDL, SQL_ENABLE_FOREIGN_KEYS, SQL_ENABLE_WAL


class Database:
    """SQLite implementation of the PROTEUS persistence contract."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._is_memory = self.db_path == ":memory:"
        self._shared_memory_conn: sqlite3.Connection | None = None
        if self._is_memory:
            # Maintain persistent connection for in-memory DB
            self._shared_memory_conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._shared_memory_conn.row_factory = sqlite3.Row
            self._shared_memory_conn.execute(SQL_ENABLE_FOREIGN_KEYS)
        self.initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if self._is_memory and self._shared_memory_conn:
            yield self._shared_memory_conn
        else:
            conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            conn.row_factory = sqlite3.Row
            conn.execute(SQL_ENABLE_FOREIGN_KEYS)
            try:
                yield conn
            finally:
                conn.close()

    def initialize(self) -> None:
        """Run DDL and configure database."""
        with self._connection() as conn:
            if not self._is_memory:
                conn.execute(SQL_ENABLE_WAL)
            conn.executescript(SCHEMA_DDL)
            conn.commit()

    def close(self) -> None:
        """Close connection if in-memory."""
        if self._shared_memory_conn:
            self._shared_memory_conn.close()
            self._shared_memory_conn = None

    # -------------------------------------------------------------------------
    # Project Operations
    # -------------------------------------------------------------------------
    def save_project(
        self,
        project_id: str,
        name: str,
        repository_path: str,
        created_at: datetime | None = None,
    ) -> None:
        ts = (created_at or datetime.now(UTC)).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, repository_path, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    repository_path = excluded.repository_path
                """,
                (project_id, name, repository_path, ts),
            )
            conn.commit()

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT id, name, repository_path, created_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)

    def list_projects(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT id, name, repository_path, created_at
                FROM projects
                ORDER BY created_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # API Inventory Operations
    # -------------------------------------------------------------------------
    def save_inventory(self, project_id: str, inventory: ApiInventory) -> None:
        """Persist ApiInventory and its dependency/usage hierarchy."""
        with self._connection() as conn:
            # Ensure project exists
            proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not proj:
                raise ValueError(
                    f"Referenced project '{project_id}' does not exist. "
                    "Projects must be created before saving inventory."
                )

            # Clear previous discovery dependencies for this project
            conn.execute("DELETE FROM apis WHERE project_id = ?", (project_id,))

            for dep in inventory.dependencies:
                dep_id = f"{project_id}:{dep.provider}"
                conn.execute(
                    """
                    INSERT INTO apis (
                        id, project_id, provider, base_url, sdk, confidence, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dep_id,
                        project_id,
                        dep.provider,
                        dep.base_url,
                        dep.sdk,
                        dep.confidence.value,
                        inventory.created_at.isoformat(),
                    ),
                )
                for idx, usage in enumerate(dep.usages):
                    usage_id = f"{dep_id}:u{idx}:{usage.file}:{usage.line}"
                    conn.execute(
                        """
                        INSERT INTO api_usages (
                            id, api_id, operation, method, path, file, line, end_line,
                            symbol, evidence_type, confidence, context_snippet, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            usage_id,
                            dep_id,
                            usage.operation,
                            usage.method,
                            usage.path,
                            usage.file,
                            usage.line,
                            usage.end_line,
                            usage.symbol,
                            usage.evidence_type.value,
                            usage.confidence.value,
                            usage.context_snippet,
                            inventory.created_at.isoformat(),
                        ),
                    )
            conn.commit()

    def get_inventory(self, project_id: str) -> ApiInventory | None:
        """Load ApiInventory for a project."""
        with self._connection() as conn:
            proj = conn.execute(
                "SELECT repository_path, created_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if not proj:
                return None

            api_rows = conn.execute(
                "SELECT id, provider, base_url, sdk, confidence FROM apis WHERE project_id = ?",
                (project_id,),
            ).fetchall()

            dependencies: list[ApiDependency] = []
            for api_row in api_rows:
                usage_rows = conn.execute(
                    """
                    SELECT operation, method, path, file, line, end_line,
                           symbol, evidence_type, confidence, context_snippet
                    FROM api_usages WHERE api_id = ?
                    ORDER BY file, line
                    """,
                    (api_row["id"],),
                ).fetchall()

                usages = [
                    ApiUsage(
                        operation=u["operation"],
                        method=u["method"],
                        path=u["path"],
                        file=u["file"],
                        line=u["line"],
                        end_line=u["end_line"],
                        symbol=u["symbol"],
                        evidence_type=EvidenceType(u["evidence_type"]),
                        confidence=ConfidenceLevel(u["confidence"]),
                        context_snippet=u["context_snippet"],
                    )
                    for u in usage_rows
                ]

                dependencies.append(
                    ApiDependency(
                        provider=api_row["provider"],
                        base_url=api_row["base_url"],
                        sdk=api_row["sdk"],
                        confidence=ConfidenceLevel(api_row["confidence"]),
                        usages=usages,
                    )
                )

            return ApiInventory(
                project_path=proj["repository_path"],
                created_at=datetime.fromisoformat(proj["created_at"]),
                dependencies=dependencies,
            )

    # -------------------------------------------------------------------------
    # Monitoring Intent Operations
    # -------------------------------------------------------------------------
    def save_intent(self, intent: MonitoringIntent, project_id: str | None = None) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO monitoring_intents (
                    id, project_id, provider, purpose, relevant_capabilities_json,
                    target_resources_json, relevant_properties_json, evidence_json,
                    status, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    purpose = excluded.purpose,
                    relevant_capabilities_json = excluded.relevant_capabilities_json,
                    target_resources_json = excluded.target_resources_json,
                    relevant_properties_json = excluded.relevant_properties_json,
                    evidence_json = excluded.evidence_json,
                    status = excluded.status,
                    notes = excluded.notes
                """,
                (
                    intent.intent_id,
                    project_id,
                    intent.provider,
                    intent.purpose,
                    json.dumps(intent.relevant_capabilities),
                    json.dumps(intent.target_resources),
                    json.dumps(intent.relevant_properties),
                    json.dumps(intent.evidence),
                    intent.status.value,
                    intent.notes,
                    intent.created_at.isoformat(),
                ),
            )
            conn.commit()

    def get_intent(self, intent_id: str) -> MonitoringIntent | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, provider, purpose, relevant_capabilities_json,
                       target_resources_json, relevant_properties_json, evidence_json,
                       status, notes, created_at
                FROM monitoring_intents WHERE id = ?
                """,
                (intent_id,),
            ).fetchone()
            if not row:
                return None
            return MonitoringIntent(
                intent_id=row["id"],
                provider=row["provider"],
                purpose=row["purpose"],
                relevant_capabilities=json.loads(row["relevant_capabilities_json"]),
                target_resources=json.loads(row["target_resources_json"]),
                relevant_properties=json.loads(row["relevant_properties_json"]),
                evidence=json.loads(row["evidence_json"]),
                status=IntentStatus(row["status"]),
                notes=row["notes"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def list_intents(self, provider: str | None = None) -> list[MonitoringIntent]:
        with self._connection() as conn:
            if provider:
                rows = conn.execute(
                    """
                    SELECT id FROM monitoring_intents
                    WHERE provider = ?
                    ORDER BY created_at DESC
                    """,
                    (provider,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id FROM monitoring_intents ORDER BY created_at DESC"
                ).fetchall()
            intents = []
            for r in rows:
                intent = self.get_intent(r["id"])
                if intent:
                    intents.append(intent)
            return intents

    # -------------------------------------------------------------------------
    # Source Definition Operations
    # -------------------------------------------------------------------------
    def save_source(self, source: SourceDefinition, api_id: str | None = None) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO sources (
                    id, api_id, provider, source_type, location, purpose,
                    authority, collection_method, freshness_policy, is_verified,
                    validation_notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    location = excluded.location,
                    purpose = excluded.purpose,
                    authority = excluded.authority,
                    collection_method = excluded.collection_method,
                    freshness_policy = excluded.freshness_policy,
                    is_verified = excluded.is_verified,
                    validation_notes = excluded.validation_notes
                """,
                (
                    source.source_id,
                    api_id,
                    source.provider,
                    source.source_type.value,
                    source.location,
                    source.purpose,
                    source.authority.value,
                    source.collection_method.value,
                    source.freshness_policy,
                    1 if source.is_verified else 0,
                    source.validation_notes,
                    source.created_at.isoformat(),
                ),
            )
            conn.commit()

    def get_source(self, source_id: str) -> SourceDefinition | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, provider, source_type, location, purpose,
                       authority, collection_method, freshness_policy, is_verified,
                       validation_notes, created_at
                FROM sources WHERE id = ?
                """,
                (source_id,),
            ).fetchone()
            if not row:
                return None
            return SourceDefinition(
                source_id=row["id"],
                provider=row["provider"],
                source_type=SourceType(row["source_type"]),
                location=row["location"],
                purpose=row["purpose"],
                authority=AuthorityClass(row["authority"]),
                collection_method=CollectionMethod(row["collection_method"]),
                freshness_policy=row["freshness_policy"],
                is_verified=bool(row["is_verified"]),
                validation_notes=row["validation_notes"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def list_sources(self, provider: str | None = None) -> list[SourceDefinition]:
        with self._connection() as conn:
            if provider:
                rows = conn.execute(
                    "SELECT id FROM sources WHERE provider = ? ORDER BY created_at DESC",
                    (provider,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT id FROM sources ORDER BY created_at DESC").fetchall()
            sources = []
            for r in rows:
                source = self.get_source(r["id"])
                if source:
                    sources.append(source)
            return sources

    # -------------------------------------------------------------------------
    # Snapshot Operations (Immutable Evidence Store)
    # -------------------------------------------------------------------------
    def save_snapshot(self, snapshot: RawSnapshot) -> None:
        """Persist RawSnapshot ensuring append-only immutability.

        Contract Section 10 & TDD Table 16:
        Never overwrite prior snapshots. Snapshots are immutable evidence.
        """
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT id FROM snapshots WHERE id = ?", (snapshot.snapshot_id,)
            ).fetchone()
            if existing:
                raise ValueError(
                    f"Snapshot {snapshot.snapshot_id} already exists. "
                    "Snapshots are immutable and cannot be overwritten."
                )

            # Ensure referenced source exists
            src = conn.execute(
                "SELECT id FROM sources WHERE id = ?", (snapshot.source_id,)
            ).fetchone()
            if not src:
                raise ValueError(
                    f"Referenced source '{snapshot.source_id}' does not exist. "
                    "Sources must be registered before saving snapshots."
                )

            conn.execute(
                """
                INSERT INTO snapshots (
                    id, source_id, retrieved_at, content_hash, status_code,
                    etag, last_modified, content_type, raw_content, fetch_status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.source_id,
                    snapshot.retrieved_at.isoformat(),
                    snapshot.content_hash,
                    snapshot.status_code,
                    snapshot.etag,
                    snapshot.last_modified,
                    snapshot.content_type,
                    snapshot.raw_content,
                    snapshot.fetch_status.value,
                    snapshot.error_message,
                ),
            )
            conn.commit()

    def get_snapshot(self, snapshot_id: str) -> RawSnapshot | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, source_id, retrieved_at, content_hash, status_code,
                       etag, last_modified, content_type, raw_content,
                       fetch_status, error_message
                FROM snapshots WHERE id = ?
                """,
                (snapshot_id,),
            ).fetchone()
            if not row:
                return None
            return RawSnapshot(
                snapshot_id=row["id"],
                source_id=row["source_id"],
                retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
                content_hash=row["content_hash"],
                status_code=row["status_code"],
                etag=row["etag"],
                last_modified=row["last_modified"],
                content_type=row["content_type"],
                raw_content=row["raw_content"],
                fetch_status=FetchStatus(row["fetch_status"]),
                error_message=row["error_message"],
            )

    def get_latest_snapshot(self, source_id: str) -> RawSnapshot | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id FROM snapshots
                WHERE source_id = ?
                ORDER BY retrieved_at DESC
                LIMIT 1
                """,
                (source_id,),
            ).fetchone()
            if not row:
                return None
            return self.get_snapshot(row["id"])

    def list_snapshots(self, source_id: str | None = None) -> list[RawSnapshot]:
        with self._connection() as conn:
            if source_id:
                rows = conn.execute(
                    "SELECT id FROM snapshots WHERE source_id = ? ORDER BY retrieved_at DESC",
                    (source_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id FROM snapshots ORDER BY retrieved_at DESC"
                ).fetchall()
            snapshots = []
            for r in rows:
                snap = self.get_snapshot(r["id"])
                if snap:
                    snapshots.append(snap)
            return snapshots

    # -------------------------------------------------------------------------
    # Normalized Contract Operations
    # -------------------------------------------------------------------------
    def save_contract(self, contract: NormalizedContract) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO contracts (
                    id, snapshot_id, provider, schema_version, state_nature,
                    normalized_json, normalized_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    schema_version = excluded.schema_version,
                    state_nature = excluded.state_nature,
                    normalized_json = excluded.normalized_json,
                    normalized_at = excluded.normalized_at
                """,
                (
                    contract.contract_id,
                    contract.snapshot_id,
                    contract.provider,
                    contract.schema_version,
                    contract.state_nature.value,
                    contract.model_dump_json(),
                    contract.normalized_at.isoformat(),
                ),
            )
            conn.commit()

    def get_contract(self, contract_id: str) -> NormalizedContract | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT normalized_json FROM contracts WHERE id = ?", (contract_id,)
            ).fetchone()
            if not row:
                return None
            return NormalizedContract.model_validate_json(row["normalized_json"])

    def get_contract_by_snapshot(self, snapshot_id: str) -> NormalizedContract | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT normalized_json FROM contracts
                WHERE snapshot_id = ?
                ORDER BY normalized_at DESC
                LIMIT 1
                """,
                (snapshot_id,),
            ).fetchone()
            if not row:
                return None
            return NormalizedContract.model_validate_json(row["normalized_json"])

    # -------------------------------------------------------------------------
    # Change Event Operations
    # -------------------------------------------------------------------------
    def save_change(self, change: ChangeEvent) -> None:
        """Persist ChangeEvent ensuring append-only audit semantics."""
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT id FROM changes WHERE id = ?", (change.change_id,)
            ).fetchone()
            if existing:
                raise ValueError(
                    f"ChangeEvent {change.change_id} already exists. "
                    "Change events are audit records and cannot be overwritten."
                )

            conn.execute(
                """
                INSERT INTO changes (
                    id, old_snapshot_id, new_snapshot_id, provider, target,
                    change_category, change_type, severity, old_state_json,
                    new_state_json, evidence_refs_json, detected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    change.change_id,
                    change.old_snapshot_id,
                    change.new_snapshot_id,
                    change.provider,
                    change.target,
                    change.change_category.value,
                    change.change_type,
                    change.severity.value,
                    json.dumps(change.old_state) if change.old_state is not None else None,
                    json.dumps(change.new_state) if change.new_state is not None else None,
                    json.dumps(change.evidence_references),
                    change.detected_at.isoformat(),
                ),
            )
            conn.commit()

    def get_change(self, change_id: str) -> ChangeEvent | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, old_snapshot_id, new_snapshot_id, provider, target,
                       change_category, change_type, severity, old_state_json,
                       new_state_json, evidence_refs_json, detected_at
                FROM changes WHERE id = ?
                """,
                (change_id,),
            ).fetchone()
            if not row:
                return None
            return ChangeEvent(
                change_id=row["id"],
                old_snapshot_id=row["old_snapshot_id"],
                new_snapshot_id=row["new_snapshot_id"],
                provider=row["provider"],
                target=row["target"],
                change_category=ChangeCategory(row["change_category"]),
                change_type=row["change_type"],
                severity=ChangeSeverity(row["severity"]),
                old_state=json.loads(row["old_state_json"]) if row["old_state_json"] else None,
                new_state=json.loads(row["new_state_json"]) if row["new_state_json"] else None,
                evidence_references=(
                    json.loads(row["evidence_refs_json"]) if row["evidence_refs_json"] else []
                ),
                detected_at=datetime.fromisoformat(row["detected_at"]),
            )

    def list_changes(self, provider: str | None = None) -> list[ChangeEvent]:
        with self._connection() as conn:
            if provider:
                rows = conn.execute(
                    "SELECT id FROM changes WHERE provider = ? ORDER BY detected_at DESC",
                    (provider,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT id FROM changes ORDER BY detected_at DESC").fetchall()
            changes = []
            for r in rows:
                c = self.get_change(r["id"])
                if c:
                    changes.append(c)
            return changes
