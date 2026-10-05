"""Discovery engine coordinating manifests, AST inspection, HTTP calls, and attribution."""

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from proteus.discovery.attribution import (
    KNOWN_PROVIDERS,
    attribute_package_name,
    compute_confidence,
)
from proteus.discovery.evidence import (
    discover_source_files,
    validate_repository_path,
)
from proteus.discovery.manifest import ManifestScanner
from proteus.discovery.python_ast import PythonAstScanner
from proteus.models.inventory import (
    ApiDependency,
    ApiInventory,
    ApiUsage,
    ConfidenceLevel,
    EvidenceType,
)
from proteus.models.uncertainty import UncertaintyState


class DiscoveryEngine:
    """Core static API discovery engine for consumer repositories."""

    def __init__(self, manifest_scanner: ManifestScanner | None = None) -> None:
        self.manifest_scanner = manifest_scanner or ManifestScanner()

    def discover(self, repo_path: str | Path) -> ApiInventory:
        """Run complete static discovery pipeline over a local repository.

        Args:
            repo_path: Path to root of repository to inspect.

        Returns:
            Validated ApiInventory containing discovered dependencies and evidence.
        """
        validated_root = validate_repository_path(repo_path)
        rel_root_str = str(validated_root)

        # Provider-keyed collections of findings
        provider_usages: dict[str, list[ApiUsage]] = defaultdict(list)
        provider_base_urls: dict[str, str] = {}
        provider_sdks: dict[str, str] = {}

        # Tracking flags for confidence evaluation per provider
        has_manifest: dict[str, bool] = defaultdict(bool)
        has_import: dict[str, bool] = defaultdict(bool)
        has_client_init: dict[str, bool] = defaultdict(bool)
        has_api_call: dict[str, bool] = defaultdict(bool)
        has_known_url: dict[str, bool] = defaultdict(bool)

        # -------------------------------------------------------------
        # Layer 1: Manifest Scanning
        # -------------------------------------------------------------
        manifest_deps = self.manifest_scanner.scan_repository(validated_root)
        for dep in manifest_deps:
            provider_id = attribute_package_name(dep.package_name)
            target_provider = provider_id or dep.package_name.lower()

            # Record if it's a known provider candidate or SDK
            if provider_id:
                has_manifest[target_provider] = True
                provider_sdks[target_provider] = dep.package_name

                provider_usages[target_provider].append(
                    ApiUsage(
                        operation="declare_dependency",
                        method=None,
                        path=None,
                        file=dep.manifest_file,
                        line=dep.line,
                        symbol=f"{dep.package_name} ({dep.section})",
                        evidence_type=EvidenceType.MANIFEST,
                        confidence=ConfidenceLevel.CANDIDATE,
                        context_snippet=f"{dep.package_name}=={dep.version_spec}"
                        if dep.version_spec
                        else dep.package_name,
                    )
                )

        # -------------------------------------------------------------
        # Layer 2 & 3: Python AST & HTTP Call Scanning
        # -------------------------------------------------------------
        files_scanned = 0
        scan_errors = 0

        for file_path in discover_source_files(validated_root, extensions={".py"}):
            files_scanned += 1
            visitor = PythonAstScanner.scan_file(validated_root, file_path)
            if visitor is None:
                scan_errors += 1
                continue

            # 2a. Imports
            for imp in visitor.imports:
                if imp.provider_id:
                    has_import[imp.provider_id] = True
                    symbol_desc = (
                        f"from {imp.module} import {imp.name}"
                        if imp.name
                        else f"import {imp.module}"
                    )
                    provider_usages[imp.provider_id].append(
                        ApiUsage(
                            operation="import",
                            method=None,
                            path=None,
                            file=imp.file,
                            line=imp.line,
                            symbol=symbol_desc,
                            evidence_type=EvidenceType.SDK_IMPORT,
                            confidence=ConfidenceLevel.CANDIDATE,
                            context_snippet=imp.snippet,
                        )
                    )

            # 2b. Client Inits
            for init in visitor.client_inits:
                if init.provider_id:
                    has_client_init[init.provider_id] = True
                    if init.base_url:
                        provider_base_urls[init.provider_id] = init.base_url

                    provider_usages[init.provider_id].append(
                        ApiUsage(
                            operation=f"{init.class_name}.__init__",
                            method=None,
                            path=None,
                            file=init.file,
                            line=init.line,
                            end_line=init.end_line,
                            symbol=f"{init.variable_name} = {init.class_name}(...)",
                            evidence_type=EvidenceType.AST_CALL,
                            confidence=ConfidenceLevel.STRONG,
                            context_snippet=init.snippet,
                        )
                    )

            # 2c. Method & HTTP Calls
            for call in visitor.calls:
                target_provider = call.provider_id or UncertaintyState.UNKNOWN.value

                if call.evidence_type == EvidenceType.HTTP_CALL:
                    if call.provider_id:
                        has_known_url[call.provider_id] = True
                        has_api_call[call.provider_id] = True
                    else:
                        has_api_call[target_provider] = True
                else:
                    if call.provider_id:
                        has_api_call[call.provider_id] = True

                provider_usages[target_provider].append(
                    ApiUsage(
                        operation=call.operation,
                        method=call.method,
                        path=call.path,
                        file=call.file,
                        line=call.line,
                        end_line=call.end_line,
                        symbol=call.symbol,
                        evidence_type=call.evidence_type,
                        confidence=call.confidence,
                        context_snippet=call.snippet,
                    )
                )

        # -------------------------------------------------------------
        # Layer 4: Synthesis & Confidence Evaluation
        # -------------------------------------------------------------
        dependencies: list[ApiDependency] = []

        for provider_id, raw_usages in provider_usages.items():
            if not raw_usages:
                continue

            # Deduplicate usages by (file, line, evidence_type, symbol)
            seen_usages: set[tuple[str, int, str, str | None]] = set()
            deduped_usages: list[ApiUsage] = []
            for u in raw_usages:
                key = (u.file, u.line, u.evidence_type.value, u.symbol)
                if key not in seen_usages:
                    seen_usages.add(key)
                    deduped_usages.append(u)

            # Sort usages deterministically by file, line
            deduped_usages.sort(key=lambda u: (u.file, u.line, u.symbol or ""))

            # Compute aggregate dependency confidence
            if provider_id == UncertaintyState.UNKNOWN.value:
                aggregate_confidence = ConfidenceLevel.UNKNOWN
                base_url = None
                sdk_name = None
            else:
                aggregate_confidence = compute_confidence(
                    has_manifest=has_manifest[provider_id],
                    has_import=has_import[provider_id],
                    has_client_init=has_client_init[provider_id],
                    has_api_call=has_api_call[provider_id],
                    has_known_url=has_known_url[provider_id],
                )
                profile = KNOWN_PROVIDERS.get(provider_id)
                base_url = provider_base_urls.get(
                    provider_id, profile.default_base_url if profile else None
                )
                sdk_name = provider_sdks.get(
                    provider_id, profile.package_names[0] if profile else None
                )

            dependencies.append(
                ApiDependency(
                    provider=provider_id,
                    base_url=base_url,
                    sdk=sdk_name,
                    confidence=aggregate_confidence,
                    usages=deduped_usages,
                )
            )

        # Deterministic ordering: CONFIRMED > STRONG > CANDIDATE > UNKNOWN
        confidence_order = {
            ConfidenceLevel.CONFIRMED: 0,
            ConfidenceLevel.STRONG: 1,
            ConfidenceLevel.CANDIDATE: 2,
            ConfidenceLevel.UNKNOWN: 3,
        }
        dependencies.sort(key=lambda d: (confidence_order.get(d.confidence, 4), d.provider))

        return ApiInventory(
            project_path=rel_root_str,
            created_at=datetime.now(UTC),
            dependencies=dependencies,
            metadata={
                "files_scanned": files_scanned,
                "scan_errors": scan_errors,
                "manifest_dependencies_count": len(manifest_deps),
                "engine_version": "0.1.0",
            },
        )
