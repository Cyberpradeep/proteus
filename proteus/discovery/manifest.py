"""Layer 1: Dependency manifest scanning across Python and Node ecosystems."""

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeclaredDependency:
    """A dependency package declared within a manifest file."""

    package_name: str
    manifest_file: str
    line: int
    version_spec: str | None = None
    section: str = "dependencies"


def _clean_pip_package_name(line: str) -> tuple[str, str | None] | None:
    """Extract package name and version specifier from a requirements.txt line."""
    cleaned = line.split("#")[0].strip()
    if not cleaned or cleaned.startswith(("-r", "-i", "-f", "--extra-index-url", "--index-url")):
        return None

    # Handle environment markers: foo >= 1.0 ; python_version > '3.8'
    if ";" in cleaned:
        cleaned = cleaned.split(";")[0].strip()

    # Split name and version comparator (==, >=, <=, ~=, !=, >, <)
    match = re.split(r"(==|>=|<=|~=|!=|>|<)", cleaned, maxsplit=1)
    if match:
        name = match[0].strip()
        version = cleaned[len(name) :].strip() if len(match) > 1 else None
        # Basic validation of package name identifier
        if re.match(r"^[A-Za-z0-9_.\-]+$", name):
            return name, version

    return None


class ManifestScanner:
    """Scans repository manifests to extract declared dependencies as candidate evidence."""

    @staticmethod
    def scan_pyproject_toml(repo_root: Path, file_path: Path) -> list[DeclaredDependency]:
        """Parse pyproject.toml dependencies (PEP 621, Poetry, Flit)."""
        results: list[DeclaredDependency] = []
        try:
            with file_path.open("rb") as f:
                data = tomllib.load(f)
        except Exception:
            return results

        rel_path = str(file_path.relative_to(repo_root)).replace("\\", "/")

        # 1. PEP 621 standard: [project.dependencies]
        project = data.get("project", {})
        deps = project.get("dependencies", [])
        if isinstance(deps, list):
            for idx, item in enumerate(deps, start=1):
                if isinstance(item, str):
                    parsed = _clean_pip_package_name(item)
                    if parsed:
                        name, version = parsed
                        results.append(
                            DeclaredDependency(
                                package_name=name,
                                manifest_file=rel_path,
                                line=idx,
                                version_spec=version,
                                section="project.dependencies",
                            )
                        )

        # 2. PEP 621 optional dependencies: [project.optional-dependencies]
        optional_deps = project.get("optional-dependencies", {})
        if isinstance(optional_deps, dict):
            for group, group_deps in optional_deps.items():
                if isinstance(group_deps, list):
                    for idx, item in enumerate(group_deps, start=1):
                        if isinstance(item, str):
                            parsed = _clean_pip_package_name(item)
                            if parsed:
                                name, version = parsed
                                results.append(
                                    DeclaredDependency(
                                        package_name=name,
                                        manifest_file=rel_path,
                                        line=idx,
                                        version_spec=version,
                                        section=f"project.optional-dependencies.{group}",
                                    )
                                )

        # 3. Poetry legacy: [tool.poetry.dependencies]
        tool = data.get("tool", {})
        poetry = tool.get("poetry", {})
        poetry_deps = poetry.get("dependencies", {})
        if isinstance(poetry_deps, dict):
            for idx, (name, spec) in enumerate(poetry_deps.items(), start=1):
                if name.lower() != "python":
                    version = spec if isinstance(spec, str) else None
                    results.append(
                        DeclaredDependency(
                            package_name=name,
                            manifest_file=rel_path,
                            line=idx,
                            version_spec=version,
                            section="tool.poetry.dependencies",
                        )
                    )

        return results

    @staticmethod
    def scan_requirements_txt(repo_root: Path, file_path: Path) -> list[DeclaredDependency]:
        """Parse pip requirements text file line by line."""
        results: list[DeclaredDependency] = []
        rel_path = str(file_path.relative_to(repo_root)).replace("\\", "/")

        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line_no, line in enumerate(f, start=1):
                    parsed = _clean_pip_package_name(line)
                    if parsed:
                        name, version = parsed
                        results.append(
                            DeclaredDependency(
                                package_name=name,
                                manifest_file=rel_path,
                                line=line_no,
                                version_spec=version,
                                section="requirements",
                            )
                        )
        except Exception:
            return results

        return results

    @staticmethod
    def scan_package_json(repo_root: Path, file_path: Path) -> list[DeclaredDependency]:
        """Parse Node package.json dependencies."""
        results: list[DeclaredDependency] = []
        rel_path = str(file_path.relative_to(repo_root)).replace("\\", "/")

        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
        except Exception:
            return results

        for section in ("dependencies", "devDependencies"):
            deps = data.get(section, {})
            if isinstance(deps, dict):
                for idx, (name, version) in enumerate(deps.items(), start=1):
                    results.append(
                        DeclaredDependency(
                            package_name=name,
                            manifest_file=rel_path,
                            line=idx,
                            version_spec=str(version) if version else None,
                            section=section,
                        )
                    )

        return results

    def scan_repository(self, repo_root: Path) -> list[DeclaredDependency]:
        """Scan all recognized dependency manifests across the repository."""
        manifest_deps: list[DeclaredDependency] = []

        # Check pyproject.toml in root or subdirectories
        for p in repo_root.glob("**/pyproject.toml"):
            if not any(
                excluded in p.parts
                for excluded in ("node_modules", ".venv", "venv", ".agent_sandbox")
            ):
                manifest_deps.extend(self.scan_pyproject_toml(repo_root, p))

        # Check requirements*.txt
        for p in repo_root.glob("**/requirements*.txt"):
            if not any(
                excluded in p.parts
                for excluded in ("node_modules", ".venv", "venv", ".agent_sandbox")
            ):
                manifest_deps.extend(self.scan_requirements_txt(repo_root, p))

        # Check requirements/*.txt
        for p in repo_root.glob("**/requirements/*.txt"):
            if not any(
                excluded in p.parts
                for excluded in ("node_modules", ".venv", "venv", ".agent_sandbox")
            ):
                manifest_deps.extend(self.scan_requirements_txt(repo_root, p))

        # Check package.json
        for p in repo_root.glob("**/package.json"):
            if not any(
                excluded in p.parts
                for excluded in ("node_modules", ".venv", "venv", ".agent_sandbox")
            ):
                manifest_deps.extend(self.scan_package_json(repo_root, p))

        return manifest_deps
