"""SQLite relational schema DDL definitions for PROTEUS."""

SQL_ENABLE_FOREIGN_KEYS = "PRAGMA foreign_keys = ON;"
SQL_ENABLE_WAL = "PRAGMA journal_mode = WAL;"

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    repository_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS apis (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    base_url TEXT,
    sdk TEXT,
    confidence TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_apis_project ON apis(project_id);

CREATE TABLE IF NOT EXISTS api_usages (
    id TEXT PRIMARY KEY,
    api_id TEXT NOT NULL,
    operation TEXT,
    method TEXT,
    path TEXT,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    end_line INTEGER,
    symbol TEXT,
    evidence_type TEXT NOT NULL,
    confidence TEXT NOT NULL,
    context_snippet TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(api_id) REFERENCES apis(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_usages_api ON api_usages(api_id);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    api_id TEXT,
    provider TEXT NOT NULL,
    source_type TEXT NOT NULL,
    location TEXT NOT NULL,
    purpose TEXT,
    authority TEXT NOT NULL,
    collection_method TEXT NOT NULL,
    freshness_policy TEXT,
    is_verified INTEGER NOT NULL DEFAULT 0,
    validation_notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(api_id) REFERENCES apis(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_provider ON sources(provider);

CREATE TABLE IF NOT EXISTS snapshots (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status_code INTEGER,
    etag TEXT,
    last_modified TEXT,
    content_type TEXT,
    raw_content TEXT NOT NULL,
    fetch_status TEXT NOT NULL,
    error_message TEXT,
    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_snapshots_source_time ON snapshots(source_id, retrieved_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_hash ON snapshots(content_hash);

CREATE TABLE IF NOT EXISTS contracts (
    id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    state_nature TEXT NOT NULL,
    normalized_json TEXT NOT NULL,
    normalized_at TEXT NOT NULL,
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_contracts_snapshot ON contracts(snapshot_id);

CREATE TABLE IF NOT EXISTS changes (
    id TEXT PRIMARY KEY,
    old_snapshot_id TEXT,
    new_snapshot_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    target TEXT NOT NULL,
    change_category TEXT NOT NULL,
    change_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    old_state_json TEXT,
    new_state_json TEXT,
    evidence_refs_json TEXT,
    detected_at TEXT NOT NULL,
    FOREIGN KEY(old_snapshot_id) REFERENCES snapshots(id) ON DELETE SET NULL,
    FOREIGN KEY(new_snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_changes_provider ON changes(provider, detected_at DESC);

CREATE TABLE IF NOT EXISTS monitoring_intents (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    provider TEXT NOT NULL,
    purpose TEXT NOT NULL,
    relevant_capabilities_json TEXT NOT NULL,
    target_resources_json TEXT NOT NULL,
    relevant_properties_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_intents_provider ON monitoring_intents(provider);
"""
