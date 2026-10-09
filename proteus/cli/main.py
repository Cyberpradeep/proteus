"""CLI interface for PROTEUS repository scanning and management."""

import argparse
import sys
from collections.abc import Sequence

import proteus
from proteus.discovery.engine import DiscoveryEngine
from proteus.models.inventory import ConfidenceLevel
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
    scan_parser.add_argument("--json", action="store_true", help="Output inventory as JSON")

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
        print(f"PROTEUS v{proteus.__version__} (Milestone A Discovery)")
        return 0

    if parsed.command == "scan":
        repo_path_input = parsed.repo_path
        try:
            engine = DiscoveryEngine()
            inventory = engine.discover(repo_path_input)
        except ValueError as e:
            print(f"[ERROR] Invalid repository path: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"[ERROR] Discovery scan failed: {e}", file=sys.stderr)
            return 1

        if getattr(parsed, "json", False):
            print(inventory.model_dump_json(indent=2))
            return 0

        # Formatted human-readable output
        print("=" * 68)
        print(" PROTEUS API DISCOVERY REPORT")
        print("=" * 68)
        print(f"Target Repository : {inventory.project_path}")
        print(f"Discovered At     : {inventory.created_at.isoformat()}")
        print(f"Files Scanned     : {inventory.metadata.get('files_scanned', 0)}")
        print(f"Scan Errors       : {inventory.metadata.get('scan_errors', 0)}")
        print(f"Total APIs Found  : {inventory.total_dependencies}")
        print(f"Total Usages      : {inventory.total_usages}")
        print("-" * 68)

        # Categorize by confidence
        confirmed = [d for d in inventory.dependencies if d.confidence == ConfidenceLevel.CONFIRMED]
        strong = [d for d in inventory.dependencies if d.confidence == ConfidenceLevel.STRONG]
        candidates = [
            d for d in inventory.dependencies if d.confidence == ConfidenceLevel.CANDIDATE
        ]
        ambiguous = [d for d in inventory.dependencies if d.confidence == ConfidenceLevel.UNKNOWN]

        if confirmed:
            print("\n[CONFIRMED API DEPENDENCIES]")
            for dep in confirmed:
                sdk_str = f" (SDK: {dep.sdk})" if dep.sdk else ""
                url_str = f" [Base: {dep.base_url}]" if dep.base_url else ""
                print(f"  * {dep.provider}{sdk_str}{url_str} - {len(dep.usages)} usage(s):")
                for u in dep.usages:
                    op_str = u.operation or u.symbol or "unknown"
                    path_str = f" path={u.path}" if u.path else ""
                    print(f"    - {u.file}:{u.line} [{u.evidence_type.value}] {op_str}{path_str}")

        if strong:
            print("\n[STRONG EVIDENCE API DEPENDENCIES]")
            for dep in strong:
                sdk_str = f" (SDK: {dep.sdk})" if dep.sdk else ""
                url_str = f" [Base: {dep.base_url}]" if dep.base_url else ""
                print(f"  * {dep.provider}{sdk_str}{url_str} - {len(dep.usages)} usage(s):")
                for u in dep.usages:
                    op_str = u.operation or u.symbol or "unknown"
                    print(f"    - {u.file}:{u.line} [{u.evidence_type.value}] {op_str}")

        if candidates:
            print("\n[CANDIDATE DEPENDENCIES (Declared / Imported Only - No Calls Observed)]")
            for dep in candidates:
                sdk_str = f" (SDK: {dep.sdk})" if dep.sdk else ""
                print(f"  * {dep.provider}{sdk_str} - {len(dep.usages)} declaration(s):")
                for u in dep.usages:
                    print(f"    - {u.file}:{u.line} [{u.evidence_type.value}] {u.symbol}")

        if ambiguous:
            print("\n[AMBIGUOUS / UNKNOWN HTTP USAGES (Unresolved Host or Dynamic Endpoint)]")
            for dep in ambiguous:
                print(f"  * {dep.provider} - {len(dep.usages)} usage(s):")
                for u in dep.usages:
                    meth_str = f"{u.method} " if u.method else ""
                    path_str = u.path or "unknown"
                    print(f"    - {u.file}:{u.line} [{u.evidence_type.value}] {meth_str}{path_str}")

        print("\n" + "=" * 68)
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
