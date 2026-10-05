"""Minimal CLI skeleton for PROTEUS foundation."""

import argparse
import sys
from collections.abc import Sequence

import proteus
from proteus.storage.database import Database


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="proteus",
        description=(
            "PROTEUS: Repository-Aware API Evolution Monitoring, "
            "Impact Analysis and Automated Repair"
        ),
    )
    parser.add_argument(
        "--db",
        default="proteus.sqlite3",
        help="Path to SQLite database file (default: proteus.sqlite3)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: version
    subparsers.add_parser("version", help="Show PROTEUS version")

    # Command: scan
    scan_parser = subparsers.add_parser("scan", help="Scan repository for API dependencies")
    scan_parser.add_argument("repo_path", help="Path to repository to scan")

    # Command: sources
    sources_parser = subparsers.add_parser("sources", help="Manage monitored API sources")
    sources_sub = sources_parser.add_subparsers(dest="sources_action", help="Source actions")
    sources_list = sources_sub.add_parser("list", help="List configured sources")
    sources_list.add_argument("--provider", help="Filter sources by provider")

    # Command: snapshots
    snapshots_parser = subparsers.add_parser("snapshots", help="Inspect raw snapshots")
    snapshots_sub = snapshots_parser.add_subparsers(
        dest="snapshots_action", help="Snapshot actions"
    )
    snapshots_list = snapshots_sub.add_parser("list", help="List snapshots")
    snapshots_list.add_argument("--source", help="Filter snapshots by source ID")

    # Command: changes
    changes_parser = subparsers.add_parser("changes", help="View detected API changes")
    changes_parser.add_argument("--provider", help="Filter changes by provider")

    return parser


def run_cli(args: Sequence[str] | None = None) -> int:
    """Execute CLI command and return exit code."""
    parser = build_parser()
    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 0

    if parsed.command == "version":
        print(f"PROTEUS v{proteus.__version__} (Milestone A Foundation)")
        return 0

    if parsed.command == "scan":
        print(f"[PROTEUS] Scanning repository: {parsed.repo_path}")
        print(
            "[NOTICE] Foundation setup active. Full API Discovery engine "
            "scheduled for Milestone A Discovery stage."
        )
        return 0

    # Commands requiring database access
    db = Database(parsed.db)

    if parsed.command == "sources":
        sources = db.list_sources(provider=getattr(parsed, "provider", None))
        if not sources:
            print("[PROTEUS] No sources found.")
            return 0
        print(f"[PROTEUS] Found {len(sources)} source(s):")
        for s in sources:
            verified_tag = "[VERIFIED]" if s.is_verified else "[UNVERIFIED]"
            print(f" - {s.source_id} ({s.provider}): {s.location} {verified_tag}")
        return 0

    if parsed.command == "snapshots":
        snapshots = db.list_snapshots(source_id=getattr(parsed, "source", None))
        if not snapshots:
            print("[PROTEUS] No snapshots found.")
            return 0
        print(f"[PROTEUS] Found {len(snapshots)} snapshot(s):")
        for snap in snapshots:
            h = snap.content_hash[:12]
            st = snap.fetch_status.value
            print(f" - {snap.snapshot_id} (source: {snap.source_id}) hash: {h} status: {st}")
        return 0

    if parsed.command == "changes":
        changes = db.list_changes(provider=getattr(parsed, "provider", None))
        if not changes:
            print("[PROTEUS] No changes detected.")
            return 0
        print(f"[PROTEUS] Found {len(changes)} change event(s):")
        for chg in changes:
            print(f" - [{chg.severity.value}] {chg.provider}: {chg.target} ({chg.change_type})")
        return 0

    return 0


def cli_entrypoint() -> None:
    """Standard console script entry point."""
    sys.exit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    cli_entrypoint()
