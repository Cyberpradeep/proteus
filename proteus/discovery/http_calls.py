"""Layer 3: Direct HTTP call discovery and endpoint URL extraction from AST."""

import ast
from dataclasses import dataclass

from proteus.discovery.attribution import attribute_url
from proteus.discovery.evidence import sanitize_code_snippet, sanitize_url
from proteus.models.inventory import ConfidenceLevel
from proteus.models.uncertainty import UncertaintyState


@dataclass
class HttpCallFinding:
    """Statically discovered HTTP request call site."""

    method: str | None
    url: str | None
    is_ambiguous: bool
    operation: str
    symbol: str
    line: int
    end_line: int | None
    snippet: str | None
    provider_id: str | None
    confidence: ConfidenceLevel


# HTTP method identifiers for common client libraries
KNOWN_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


class HttpCallExtractor:
    """Extracts direct HTTP call patterns from Python AST nodes."""

    def __init__(self, constants: dict[str, str], lines: list[str]) -> None:
        self.constants = constants
        self.lines = lines

    def _get_snippet(self, node: ast.AST) -> str | None:
        """Extract sanitized source lines for an AST node."""
        start_line = getattr(node, "lineno", None)
        if start_line is None or not (1 <= start_line <= len(self.lines)):
            return None
        end_line = getattr(node, "end_lineno", start_line)
        end_line = min(end_line or start_line, len(self.lines))
        raw_snippet = "\n".join(self.lines[start_line - 1 : end_line]).strip()
        return sanitize_code_snippet(raw_snippet)

    def _resolve_url_expr(self, expr: ast.expr) -> tuple[str | None, bool]:
        """Resolve a URL AST expression into a URL string and ambiguity flag.

        Returns:
            (resolved_url_or_template, is_ambiguous)
        """
        # 1. String literal
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return expr.value, False

        # 2. Variable name
        if isinstance(expr, ast.Name):
            var_name = expr.id
            if var_name in self.constants:
                return self.constants[var_name], False
            return UncertaintyState.AMBIGUOUS.value, True

        # 3. f-string: f"{BASE_URL}/v1/payments"
        if isinstance(expr, ast.JoinedStr):
            parts: list[str] = []
            has_unknown = False
            for part in expr.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    parts.append(part.value)
                elif isinstance(part, ast.FormattedValue):
                    val_expr = part.value
                    if isinstance(val_expr, ast.Name) and val_expr.id in self.constants:
                        parts.append(self.constants[val_expr.id])
                    elif isinstance(val_expr, ast.Name):
                        parts.append(f"{{{val_expr.id}}}")
                        has_unknown = True
                    else:
                        parts.append("{expr}")
                        has_unknown = True
                else:
                    parts.append("{expr}")
                    has_unknown = True

            combined = "".join(parts)
            return combined, has_unknown

        # 4. Binary concatenation: BASE_URL + "/v1/users"
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
            left_val, left_amb = self._resolve_url_expr(expr.left)
            right_val, right_amb = self._resolve_url_expr(expr.right)
            if left_val and right_val:
                return f"{left_val}{right_val}", (left_amb or right_amb)
            return UncertaintyState.AMBIGUOUS.value, True

        # 5. urljoin call: urljoin(BASE_URL, "path")
        if isinstance(expr, ast.Call):
            call_func = expr.func
            func_name = getattr(call_func, "id", None) or getattr(call_func, "attr", None)
            if func_name == "urljoin" and len(expr.args) >= 2:
                base, b_amb = self._resolve_url_expr(expr.args[0])
                path, p_amb = self._resolve_url_expr(expr.args[1])
                if base and path:
                    base_clean = base.rstrip("/")
                    path_clean = path.lstrip("/")
                    return f"{base_clean}/{path_clean}", (b_amb or p_amb)

        return UncertaintyState.UNKNOWN.value, True

    def extract_call(
        self,
        node: ast.Call,
        caller_name: str,
        attr_name: str,
        known_http_sessions: set[str],
    ) -> HttpCallFinding | None:
        """Inspect an AST Call node to determine if it represents an HTTP request."""
        method: str | None = None
        url_expr: ast.expr | None = None
        operation = f"{caller_name}.{attr_name}"
        symbol = operation

        # Pattern A: requests.get(url, ...), httpx.post(url, ...)
        if caller_name in ("requests", "httpx") and attr_name.lower() in KNOWN_HTTP_METHODS:
            method = attr_name.upper()
            if node.args:
                url_expr = node.args[0]
            else:
                for kw in node.keywords:
                    if kw.arg == "url":
                        url_expr = kw.value
                        break

        # Pattern B: requests.request("POST", url, ...), httpx.request(...)
        elif caller_name in ("requests", "httpx") and attr_name.lower() == "request":
            if node.args:
                # 1st arg: method
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    method = node.args[0].value.upper()
                if len(node.args) > 1:
                    url_expr = node.args[1]
            for kw in node.keywords:
                if kw.arg == "method" and isinstance(kw.value, ast.Constant):
                    method = str(kw.value.value).upper()
                elif kw.arg == "url":
                    url_expr = kw.value

        # Pattern C: session.get(...), client.post(...) for tracked HTTP sessions
        elif caller_name in known_http_sessions and attr_name.lower() in KNOWN_HTTP_METHODS:
            method = attr_name.upper()
            if node.args:
                url_expr = node.args[0]
            else:
                for kw in node.keywords:
                    if kw.arg == "url":
                        url_expr = kw.value
                        break

        # Pattern D: urllib.request.urlopen(url, ...)
        elif caller_name in ("urllib.request", "request") and attr_name == "urlopen":
            method = "GET"
            if node.args:
                url_expr = node.args[0]
            for kw in node.keywords:
                if kw.arg == "url":
                    url_expr = kw.value
                    break

        # Pattern E: urllib.request.Request(url, method=...)
        elif caller_name in ("urllib.request", "request") and attr_name == "Request":
            method = "GET"
            if node.args:
                url_expr = node.args[0]
            for kw in node.keywords:
                if kw.arg == "url":
                    url_expr = kw.value
                elif kw.arg == "method" and isinstance(kw.value, ast.Constant):
                    method = str(kw.value.value).upper()

        # Pattern F: aiohttp session calls: session.get(url), session.post(url)
        elif caller_name in known_http_sessions and attr_name.lower() in KNOWN_HTTP_METHODS:
            method = attr_name.upper()
            if node.args:
                url_expr = node.args[0]

        if method is None and url_expr is None:
            return None

        # Resolve URL
        resolved_url: str | None = None
        is_ambiguous = False
        if url_expr is not None:
            raw_url, is_ambiguous = self._resolve_url_expr(url_expr)
            resolved_url = sanitize_url(raw_url)
        else:
            resolved_url = UncertaintyState.NOT_OBSERVED.value
            is_ambiguous = True

        # Attribute provider if URL matches a known external host
        provider_id: str | None = None
        if resolved_url and not is_ambiguous:
            provider_id = attribute_url(resolved_url)

        # Confidence assessment:
        # If URL matches known provider -> STRONG / CONFIRMED
        # If URL is external but provider unknown -> CANDIDATE
        # If URL is ambiguous/dynamic -> UNKNOWN
        if provider_id is not None:
            confidence = ConfidenceLevel.STRONG if is_ambiguous else ConfidenceLevel.CONFIRMED
        elif is_ambiguous:
            confidence = ConfidenceLevel.UNKNOWN
        else:
            confidence = ConfidenceLevel.CANDIDATE

        snippet = self._get_snippet(node)

        return HttpCallFinding(
            method=method,
            url=resolved_url,
            is_ambiguous=is_ambiguous,
            operation=operation,
            symbol=symbol,
            line=getattr(node, "lineno", 1),
            end_line=getattr(node, "end_lineno", None),
            snippet=snippet,
            provider_id=provider_id,
            confidence=confidence,
        )


def extract_module_constants(tree: ast.Module) -> dict[str, str]:
    """Extract top-level string constants e.g. BASE_URL = 'https://api.stripe.com'."""
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                var_name = node.targets[0].id
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    constants[var_name] = node.value.value
    return constants
