"""Unit tests for PROTEUS minimal CLI skeleton."""

import tempfile
from pathlib import Path

import pytest

from proteus.cli.main import run_cli
from proteus.models import RawSnapshot, SourceDefinition, SourceType
from proteus.storage.database import Database


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["version"])
    assert code == 0
    captured = capsys.readouterr()
    assert "PROTEUS v" in captured.out


def test_cli_scan_human_report(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["scan", "tests/fixtures/sample_repo"])
    assert code == 0
    captured = capsys.readouterr()
    assert "PROTEUS API DISCOVERY REPORT" in captured.out
    assert "[CONFIRMED API DEPENDENCIES]" in captured.out
    assert "google_gemini" in captured.out
    assert "openai" in captured.out
    assert "stripe" in captured.out
    assert "[CANDIDATE DEPENDENCIES" in captured.out
    assert "anthropic" in captured.out
    assert "[AMBIGUOUS / UNKNOWN HTTP USAGES" in captured.out


def test_cli_scan_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["scan", "tests/fixtures/sample_repo", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    import json

    data = json.loads(captured.out)
    assert "project_path" in data
    assert "dependencies" in data
    assert any(d["provider"] == "google_gemini" for d in data["dependencies"])


def test_cli_scan_invalid_path(capsys: pytest.CaptureFixture[str]) -> None:
    code = run_cli(["scan", "nonexistent/path/nowhere"])
    assert code == 1
    captured = capsys.readouterr()
    assert "[ERROR] Invalid repository path" in captured.err


def test_cli_sources_list(capsys: pytest.CaptureFixture[str]) -> None:
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tf:
        db_path = tf.name

    try:
        db = Database(db_path)
        src = SourceDefinition(
            source_id="src-cli-test",
            provider="gemini",
            source_type=SourceType.LIVE_RESOURCE,
            location="https://api.example.com",
            is_verified=True,
        )
        db.save_source(src)
        db.close()

        code = run_cli(["--db", db_path, "sources", "list"])
        assert code == 0
        captured = capsys.readouterr()
        assert "src-cli-test" in captured.out
        assert "[VERIFIED]" in captured.out
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_cli_snapshots_and_changes(capsys: pytest.CaptureFixture[str]) -> None:
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tf:
        db_path = tf.name

    try:
        db = Database(db_path)
        db.save_source(
            SourceDefinition(
                source_id="src-cli",
                provider="test_provider",
                source_type=SourceType.LIVE_RESOURCE,
                location="https://api.example.com",
            )
        )
        snap = RawSnapshot.create_from_content("src-cli", "test payload")
        db.save_snapshot(snap)
        db.close()

        code = run_cli(["--db", db_path, "snapshots", "list"])
        assert code == 0
        captured = capsys.readouterr()
        assert snap.snapshot_id in captured.out

        code = run_cli(["--db", db_path, "changes"])
        assert code == 0
        captured = capsys.readouterr()
        assert "No changes detected" in captured.out
    finally:
        Path(db_path).unlink(missing_ok=True)
