"""Extensible provider attribution registry and confidence evaluation rules."""

from dataclasses import dataclass, field
from urllib.parse import urlparse

from proteus.models.inventory import ConfidenceLevel


@dataclass(frozen=True)
class ProviderProfile:
    """Attribution metadata for a recognized third-party API provider."""

    provider_id: str
    display_name: str
    package_names: list[str] = field(default_factory=list)
    import_modules: list[str] = field(default_factory=list)
    client_classes: list[str] = field(default_factory=list)
    known_hosts: list[str] = field(default_factory=list)
    default_base_url: str | None = None
    common_operations: list[str] = field(default_factory=list)


# Registry of recognized external providers
KNOWN_PROVIDERS: dict[str, ProviderProfile] = {
    "google_gemini": ProviderProfile(
        provider_id="google_gemini",
        display_name="Google Gemini / Vertex AI",
        package_names=["google-genai", "google-generativeai"],
        import_modules=["google.genai", "google.generativeai"],
        client_classes=["Client", "GenerativeModel"],
        known_hosts=["generativelanguage.googleapis.com", "aiplatform.googleapis.com"],
        default_base_url="https://generativelanguage.googleapis.com",
        common_operations=["generate_content", "embed_content", "count_tokens"],
    ),
    "openai": ProviderProfile(
        provider_id="openai",
        display_name="OpenAI API",
        package_names=["openai"],
        import_modules=["openai"],
        client_classes=["OpenAI", "AsyncOpenAI", "AzureOpenAI"],
        known_hosts=["api.openai.com"],
        default_base_url="https://api.openai.com/v1",
        common_operations=["chat.completions.create", "embeddings.create", "models.list"],
    ),
    "stripe": ProviderProfile(
        provider_id="stripe",
        display_name="Stripe Payments API",
        package_names=["stripe"],
        import_modules=["stripe"],
        client_classes=["StripeClient"],
        known_hosts=["api.stripe.com"],
        default_base_url="https://api.stripe.com",
        common_operations=["PaymentIntent.create", "Charge.create", "Customer.create"],
    ),
    "anthropic": ProviderProfile(
        provider_id="anthropic",
        display_name="Anthropic Claude API",
        package_names=["anthropic"],
        import_modules=["anthropic"],
        client_classes=["Anthropic", "AsyncAnthropic"],
        known_hosts=["api.anthropic.com"],
        default_base_url="https://api.anthropic.com",
        common_operations=["messages.create"],
    ),
    "github": ProviderProfile(
        provider_id="github",
        display_name="GitHub REST API",
        package_names=["pygithub", "github"],
        import_modules=["github"],
        client_classes=["Github"],
        known_hosts=["api.github.com"],
        default_base_url="https://api.github.com",
        common_operations=["get_repo", "get_user"],
    ),
}

# Generic HTTP libraries that do not identify a provider by themselves
HTTP_LIBRARIES = {
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "urllib",
    "http.client",
}

# Common development, testing, and build tools that are not external service APIs
DEV_AND_BUILD_TOOLS = {
    "pytest",
    "pytest-asyncio",
    "mypy",
    "ruff",
    "black",
    "flake8",
    "tox",
    "wheel",
    "setuptools",
    "hatchling",
    "flit",
    "isort",
    "coverage",
    "pylint",
    "bandit",
    "pre-commit",
    "twine",
    "build",
}


def is_dev_tool(package_name: str) -> bool:
    """Check if declared package is a standard build/test/lint tool rather than an API."""
    normalized = package_name.lower().replace("_", "-")
    return normalized in DEV_AND_BUILD_TOOLS or normalized.startswith(
        ("pytest-", "flake8-", "mypy-")
    )


def is_stdlib_module(module_name: str) -> bool:
    """Check if imported module belongs to the Python standard library."""
    import sys

    root_module = module_name.split(".")[0]
    return root_module in sys.stdlib_module_names and not is_http_library(root_module)


def attribute_package_name(package_name: str) -> str | None:
    """Map a package name from a dependency manifest to a provider ID."""
    normalized = package_name.lower().replace("_", "-")
    for provider_id, profile in KNOWN_PROVIDERS.items():
        for pkg in profile.package_names:
            if pkg.lower().replace("_", "-") == normalized:
                return provider_id
    return None


def attribute_import_module(module_name: str) -> str | None:
    """Map an imported module path to a known provider ID."""
    for provider_id, profile in KNOWN_PROVIDERS.items():
        for mod in profile.import_modules:
            if module_name == mod or module_name.startswith(f"{mod}."):
                return provider_id
    return None


def attribute_url(url: str) -> str | None:
    """Map a URL or host to a known provider ID based on hostname."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            # Handle cases where URL literal starts without scheme, e.g. api.stripe.com/v1
            first_part = url.split("/")[0].lower()
            if "." in first_part:
                host = first_part

        for provider_id, profile in KNOWN_PROVIDERS.items():
            for known_host in profile.known_hosts:
                if host == known_host or host.endswith(f".{known_host}"):
                    return provider_id
    except Exception:
        return None

    return None


def is_http_library(module_name: str) -> bool:
    """Check if imported module is a generic HTTP client library."""
    root_module = module_name.split(".")[0]
    return root_module in HTTP_LIBRARIES


def compute_confidence(
    has_manifest: bool,
    has_import: bool,
    has_client_init: bool,
    has_api_call: bool,
    has_known_url: bool,
) -> ConfidenceLevel:
    """Determine confidence level using evidence accumulation.

    Contract: Package presence is candidate; confirmed requires call evidence.
    """
    # Multiple converging operational proofs
    if (has_client_init and has_api_call) or (has_api_call and has_known_url):
        return ConfidenceLevel.CONFIRMED

    # Strong single evidence: direct client init or known URL call
    if has_client_init or has_known_url or (has_import and has_api_call):
        return ConfidenceLevel.STRONG

    # Candidate only: imported or declared in manifest, but no calls observed
    if has_import or has_manifest:
        return ConfidenceLevel.CANDIDATE

    return ConfidenceLevel.UNKNOWN
