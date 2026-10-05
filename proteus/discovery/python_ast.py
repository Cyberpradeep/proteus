"""Layer 2: Python static discovery inspecting imports, client inits, and API calls."""

import ast
from dataclasses import dataclass
from pathlib import Path

from proteus.discovery.attribution import (
    KNOWN_PROVIDERS,
    attribute_import_module,
    is_http_library,
)
from proteus.discovery.evidence import sanitize_code_snippet, sanitize_url
from proteus.discovery.http_calls import HttpCallExtractor, extract_module_constants
from proteus.models.inventory import ConfidenceLevel, EvidenceType


@dataclass
class AstImportFinding:
    """Import statement found in Python source."""

    module: str
    name: str | None
    alias: str | None
    line: int
    file: str
    provider_id: str | None
    snippet: str | None


@dataclass
class AstClientInitFinding:
    """Client constructor invocation e.g. client = OpenAI(...)."""

    variable_name: str
    class_name: str
    base_url: str | None
    line: int
    end_line: int | None
    file: str
    provider_id: str | None
    snippet: str | None


@dataclass
class AstCallFinding:
    """Method invocation or API request call site."""

    operation: str
    symbol: str
    line: int
    end_line: int | None
    file: str
    provider_id: str | None
    evidence_type: EvidenceType
    confidence: ConfidenceLevel
    snippet: str | None
    method: str | None = None
    path: str | None = None


def get_attribute_chain(node: ast.AST) -> str | None:
    """Convert an AST expression into a dot-separated attribute chain.

    e.g. client.models.generate_content -> 'client.models.generate_content'
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        value_chain = get_attribute_chain(node.value)
        if value_chain:
            return f"{value_chain}.{node.attr}"
        return node.attr
    if isinstance(node, ast.Call):
        func_chain = get_attribute_chain(node.func)
        if func_chain:
            return f"{func_chain}()"
    return None


class PythonSourceVisitor(ast.NodeVisitor):
    """AST visitor traversing a single Python source file for API usages."""

    def __init__(
        self,
        repo_root: Path,
        file_path: Path,
        lines: list[str],
        constants: dict[str, str],
    ) -> None:
        self.repo_root = repo_root
        self.file_path = file_path
        self.rel_file = str(file_path.relative_to(repo_root)).replace("\\", "/")
        self.lines = lines
        self.constants = constants

        # Tracked mappings for resolution
        self.imported_modules: dict[str, str] = {}  # alias/name -> full module
        self.imported_names: dict[
            str, tuple[str, str]
        ] = {}  # local_name -> (module, original_name)
        self.assigned_clients: dict[
            str, tuple[str, str, str | None]
        ] = {}  # var_name -> (provider_id, class_name, base_url)
        self.known_http_sessions: set[str] = set()

        # Findings collected
        self.imports: list[AstImportFinding] = []
        self.client_inits: list[AstClientInitFinding] = []
        self.calls: list[AstCallFinding] = []

        self.http_extractor = HttpCallExtractor(constants=self.constants, lines=self.lines)

    def _get_snippet(self, node: ast.AST) -> str | None:
        start_line = getattr(node, "lineno", None)
        if start_line is None or not (1 <= start_line <= len(self.lines)):
            return None
        end_line = getattr(node, "end_lineno", start_line)
        end_line = min(end_line or start_line, len(self.lines))
        raw_snippet = "\n".join(self.lines[start_line - 1 : end_line]).strip()
        return sanitize_code_snippet(raw_snippet)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            mod_name = alias.name
            as_name = alias.asname or mod_name
            self.imported_modules[as_name] = mod_name

            provider_id = attribute_import_module(mod_name)
            snippet = self._get_snippet(node)

            self.imports.append(
                AstImportFinding(
                    module=mod_name,
                    name=None,
                    alias=alias.asname,
                    line=node.lineno,
                    file=self.rel_file,
                    provider_id=provider_id,
                    snippet=snippet,
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod_name = node.module or ""
        for alias in node.names:
            item_name = alias.name
            as_name = alias.asname or item_name
            full_path = f"{mod_name}.{item_name}" if mod_name else item_name
            self.imported_names[as_name] = (mod_name, item_name)
            self.imported_modules[as_name] = full_path

            provider_id = attribute_import_module(mod_name) or attribute_import_module(full_path)
            snippet = self._get_snippet(node)

            self.imports.append(
                AstImportFinding(
                    module=mod_name,
                    name=item_name,
                    alias=alias.asname,
                    line=node.lineno,
                    file=self.rel_file,
                    provider_id=provider_id,
                    snippet=snippet,
                )
            )
        self.generic_visit(node)

    def _register_client_assignment(
        self, var_name: str, call_node: ast.Call, node_for_snippet: ast.AST
    ) -> None:
        """Register tracked HTTP sessions or SDK client variables."""
        chain = get_attribute_chain(call_node.func)
        if not chain:
            return

        # Check for HTTP session creation: session = requests.Session(), client = httpx.Client()
        if chain in (
            "requests.Session",
            "httpx.Client",
            "httpx.AsyncClient",
            "aiohttp.ClientSession",
        ) or is_http_library(chain.split(".")[0]):
            self.known_http_sessions.add(var_name)
            return

        # Check for SDK client instantiation
        base_url: str | None = None
        for kw in call_node.keywords:
            if (
                kw.arg in ("base_url", "api_base")
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                base_url = sanitize_url(kw.value.value)

        # Resolve constructor class and provider
        provider_id: str | None = None
        class_name = chain.split(".")[-1]

        # Match 1: Imported class name e.g. from openai import OpenAI -> client = OpenAI()
        if chain in self.imported_names:
            source_mod, orig_name = self.imported_names[chain]
            provider_id = attribute_import_module(source_mod) or attribute_import_module(
                f"{source_mod}.{orig_name}"
            )
            class_name = orig_name

        # Match 2: Dot notation e.g. client = genai.Client() where genai is imported module
        elif "." in chain:
            parts = chain.split(".")
            caller = parts[0]
            resolved_mod = self.imported_modules.get(caller, caller)
            provider_id = attribute_import_module(resolved_mod)

        # Match 3: Direct check against known unique client classes only if imported
        elif chain in self.imported_modules:
            provider_id = attribute_import_module(self.imported_modules[chain])

        if provider_id:
            self.assigned_clients[var_name] = (provider_id, class_name, base_url)
            snippet = self._get_snippet(node_for_snippet)
            self.client_inits.append(
                AstClientInitFinding(
                    variable_name=var_name,
                    class_name=class_name,
                    base_url=base_url,
                    line=getattr(node_for_snippet, "lineno", 1),
                    end_line=getattr(node_for_snippet, "end_lineno", None),
                    file=self.rel_file,
                    provider_id=provider_id,
                    snippet=snippet,
                )
            )

    def visit_Assign(self, node: ast.Assign) -> None:
        """Detect client construction assignments e.g. client = OpenAI(...)."""
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
        ):
            self._register_client_assignment(node.targets[0].id, node.value, node)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        """Detect context manager client assignments e.g. with httpx.Client() as client:."""
        for item in node.items:
            if isinstance(item.optional_vars, ast.Name) and isinstance(item.context_expr, ast.Call):
                self._register_client_assignment(item.optional_vars.id, item.context_expr, node)
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        """Detect async context manager client assignments."""
        for item in node.items:
            if isinstance(item.optional_vars, ast.Name) and isinstance(item.context_expr, ast.Call):
                self._register_client_assignment(item.optional_vars.id, item.context_expr, node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Inspect calls for API operations or HTTP requests."""
        chain = get_attribute_chain(node.func)
        if not chain:
            self.generic_visit(node)
            return

        parts = chain.split(".")
        caller = parts[0]
        attr = parts[-1] if len(parts) > 1 else ""

        # Check 1: Direct HTTP call via requests / httpx / urllib / session
        http_finding = self.http_extractor.extract_call(
            node=node,
            caller_name=caller,
            attr_name=attr,
            known_http_sessions=self.known_http_sessions,
        )
        if http_finding:
            self.calls.append(
                AstCallFinding(
                    operation=http_finding.operation,
                    symbol=http_finding.symbol,
                    line=http_finding.line,
                    end_line=http_finding.end_line,
                    file=self.rel_file,
                    provider_id=http_finding.provider_id,
                    evidence_type=EvidenceType.HTTP_CALL,
                    confidence=http_finding.confidence,
                    snippet=http_finding.snippet,
                    method=http_finding.method,
                    path=http_finding.url,
                )
            )
            self.generic_visit(node)
            return

        # Check 2: Method call on assigned client instance (e.g. client.generate_content)
        if caller in self.assigned_clients and len(parts) > 1:
            provider_id, class_name, _ = self.assigned_clients[caller]
            sub_op = ".".join(parts[1:])
            operation = f"{class_name}.{sub_op}"
            snippet = self._get_snippet(node)

            self.calls.append(
                AstCallFinding(
                    operation=operation,
                    symbol=chain,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", None),
                    file=self.rel_file,
                    provider_id=provider_id,
                    evidence_type=EvidenceType.AST_CALL,
                    confidence=ConfidenceLevel.CONFIRMED,
                    snippet=snippet,
                    method=None,
                    path=sub_op,
                )
            )
            self.generic_visit(node)
            return

        # Check 3: Direct module API calls (e.g. stripe.PaymentIntent.create)
        resolved_caller = self.imported_modules.get(caller, caller)
        direct_provider_id: str | None = attribute_import_module(resolved_caller)

        if not direct_provider_id and caller in self.imported_names:
            source_mod, _ = self.imported_names[caller]
            direct_provider_id = attribute_import_module(source_mod)

        if direct_provider_id and len(parts) > 1 and not is_http_library(resolved_caller):
            sub_op = ".".join(parts[1:])
            profile = KNOWN_PROVIDERS.get(direct_provider_id)
            if profile and sub_op in profile.client_classes:
                self.generic_visit(node)
                return

            snippet = self._get_snippet(node)

            self.calls.append(
                AstCallFinding(
                    operation=sub_op,
                    symbol=chain,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", None),
                    file=self.rel_file,
                    provider_id=direct_provider_id,
                    evidence_type=EvidenceType.AST_CALL,
                    confidence=ConfidenceLevel.CONFIRMED,
                    snippet=snippet,
                    method=None,
                    path=sub_op,
                )
            )

        self.generic_visit(node)


class PythonAstScanner:
    """Scanner for Python AST analysis over repository files."""

    @staticmethod
    def scan_file(repo_root: Path, file_path: Path) -> PythonSourceVisitor | None:
        """Parse and scan a single Python file, returning collected visitor findings."""
        try:
            with file_path.open("r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return None

        lines = content.splitlines()

        try:
            tree = ast.parse(content, filename=str(file_path))
        except (SyntaxError, ValueError):
            # Gracefully handle malformed Python files without crashing discovery
            return None

        constants = extract_module_constants(tree)
        visitor = PythonSourceVisitor(
            repo_root=repo_root,
            file_path=file_path,
            lines=lines,
            constants=constants,
        )
        visitor.visit(tree)
        return visitor
