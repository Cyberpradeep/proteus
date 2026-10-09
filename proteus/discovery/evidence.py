"""Evidence sanitization, secret redaction, and repository traversal safety."""

import os
import re
from collections.abc import Iterator
from pathlib import Path

# Directories to strictly exclude from repository discovery
EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "target",
    ".agent_sandbox",
    "site-packages",
}

# File extensions to ignore (binaries, compiled code, media, archives)
IGNORED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".ico",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".sqlite3-wal",
    ".sqlite3-shm",
}

# Regex patterns for detecting and redacting secrets in code and URLs
SECRET_PATTERNS = [
    # Bearer tokens
    (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{12,}", re.IGNORECASE), r"\1[REDACTED]"),
    # Generic API key assignments: api_key = "...", token = "..."
    (
        re.compile(
            r"""((?:api[_-]?key|access[_-]?token|auth[_-]?token|secret|password)\s*[:=]\s*['"])[^'"]{8,}(['"])""",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\2",
    ),
    # OpenAI key pattern: sk-...
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "sk-[REDACTED]"),
    # Google API key pattern: AIza...
    (re.compile(r"AIza[0-9A-Za-z-_]{35}"), "AIza[REDACTED]"),
    # GitHub token pattern: ghp_..., gho_..., ghu_...
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"), "ghp_[REDACTED]"),
    # Slack token pattern: xox[baprs]-...
    (re.compile(r"xox[baprs]-[0-9A-Za-z-]{20,}"), "xox-[REDACTED]"),
    # URL query parameter secrets: ?key=..., &token=..., &secret=...
    (
        re.compile(
            r"([?&](?:key|api_key|token|access_token|secret|password)=)[^&\s'\"]+",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
]


def validate_repository_path(path: str | Path) -> Path:
    """Validate that repository path exists, is a directory, and resolve it safely.

    Raises:
        ValueError: If path does not exist or is not a directory.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise ValueError(f"Repository path does not exist: {path}")
    if not p.is_dir():
        raise ValueError(f"Repository path is not a directory: {path}")
    return p


def is_binary_file(file_path: Path) -> bool:
    """Check if file is binary by sniffing for null bytes in initial chunk."""
    try:
        with file_path.open("rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except OSError:
        return True


def discover_source_files(repo_root: Path, extensions: set[str] | None = None) -> Iterator[Path]:
    """Safely traverse repository root yielding relevant source files.

    Excludes standard cache/build directories, binaries, and symlinks escaping the repo.
    """
    repo_root = repo_root.resolve()

    for root, dirs, files in os.walk(repo_root, followlinks=False):
        # Prune excluded directories in-place to prevent os.walk from recursing into them
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]

        current_root = Path(root)

        # Protect against symlink escapes
        try:
            resolved_root = current_root.resolve()
            if not resolved_root.is_relative_to(repo_root):
                continue
        except (ValueError, OSError):
            continue

        for file_name in files:
            file_path = current_root / file_name

            # Check ignored extensions
            if file_path.suffix.lower() in IGNORED_EXTENSIONS:
                continue

            if extensions is not None and file_path.suffix.lower() not in extensions:
                continue

            # Skip binary files
            if is_binary_file(file_path):
                continue

            yield file_path


def sanitize_code_snippet(snippet: str | None) -> str | None:
    """Redact sensitive keys, tokens, and authorization secrets from code snippets."""
    if snippet is None:
        return None

    sanitized = snippet
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    return sanitized


def sanitize_url(url: str | None) -> str | None:
    """Redact sensitive query params and user-info from URLs."""
    if url is None:
        return None

    sanitized = url
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    # Redact basic auth in URLs: http://user:pass@host -> http://[REDACTED]@host
    sanitized = re.sub(r"(https?://)[^/@\s]+@", r"\1[REDACTED]@", sanitized)
    return sanitized
