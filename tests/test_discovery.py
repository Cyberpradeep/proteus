"""Comprehensive behavioral test suite for PROTEUS API Discovery engine."""

import json
import tempfile
from pathlib import Path

import pytest

from proteus.discovery.attribution import (
    attribute_package_name,
    attribute_url,
    compute_confidence,
)
from proteus.discovery.engine import DiscoveryEngine
from proteus.discovery.evidence import (
    discover_source_files,
    sanitize_code_snippet,
    sanitize_url,
    validate_repository_path,
)
from proteus.discovery.manifest import ManifestScanner
from proteus.discovery.python_ast import PythonAstScanner
from proteus.models.inventory import ConfidenceLevel, EvidenceType
from proteus.models.uncertainty import UncertaintyState

SAMPLE_REPO_PATH = Path("tests/fixtures/sample_repo").resolve()
MALFORMED_REPO_PATH = Path("tests/fixtures/malformed_repo").resolve()
REAL_REPO_PATH = Path("tests/fixtures/real_repo").resolve()


# =========================================================================
# LAYER 1: Manifest Scanning Tests
# =========================================================================
class TestManifestScanning:
    """Tests for Layer 1 manifest dependency extraction."""

    def test_pyproject_dependencies_detected(self) -> None:
        scanner = ManifestScanner()
        deps = scanner.scan_repository(SAMPLE_REPO_PATH)
        pkg_names = {d.package_name for d in deps}

        assert "google-genai" in pkg_names
        assert "openai" in pkg_names
        assert "stripe" in pkg_names
        assert "anthropic" in pkg_names
        assert "httpx" in pkg_names
        assert "requests" in pkg_names

        # Line numbers must be positive
        for dep in deps:
            assert dep.line >= 1
            assert "pyproject.toml" in dep.manifest_file

    def test_pyproject_poetry_and_optional_dependencies(self) -> None:
        content = """
[tool.poetry.dependencies]
python = "^3.11"
stripe = "^10.0.0"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "openai>=1.0.0"
]
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            p = tmp_path / "pyproject.toml"
            p.write_text(content, encoding="utf-8")

            scanner = ManifestScanner()
            deps = scanner.scan_pyproject_toml(tmp_path, p)
            pkg_map = {d.package_name: d for d in deps}

            assert "stripe" in pkg_map
            assert pkg_map["stripe"].section == "tool.poetry.dependencies"
            assert "openai" in pkg_map
            assert "dev" in pkg_map["openai"].section

    def test_requirements_txt_parsing(self) -> None:
        content = """
# Production requirements
google-genai>=0.1.0 ; python_version > '3.8'
openai==1.12.0 # Inline comment
-r other-requirements.txt
--index-url https://pypi.org/simple
stripe~=7.0
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            req_file = tmp_path / "requirements.txt"
            req_file.write_text(content, encoding="utf-8")

            scanner = ManifestScanner()
            deps = scanner.scan_requirements_txt(tmp_path, req_file)
            names = [d.package_name for d in deps]

            assert "google-genai" in names
            assert "openai" in names
            assert "stripe" in names
            assert len(deps) == 3

    def test_package_json_parsing(self) -> None:
        content = {
            "dependencies": {"@google/genai": "^0.1.0", "openai": "^4.0.0"},
            "devDependencies": {"typescript": "^5.0.0"},
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pkg_file = tmp_path / "package.json"
            pkg_file.write_text(json.dumps(content), encoding="utf-8")

            scanner = ManifestScanner()
            deps = scanner.scan_package_json(tmp_path, pkg_file)
            pkg_map = {d.package_name: d for d in deps}

            assert "@google/genai" in pkg_map
            assert "openai" in pkg_map
            assert "typescript" in pkg_map


# =========================================================================
# LAYER 2 & 3: Python AST & Direct HTTP Tests
# =========================================================================
class TestPythonAstAndHttpDiscovery:
    """Tests for Python AST analysis, client instantiation, and HTTP calls."""

    def test_import_and_client_init_detection(self) -> None:
        visitor = PythonAstScanner.scan_file(
            SAMPLE_REPO_PATH, SAMPLE_REPO_PATH / "src" / "ai_service.py"
        )
        assert visitor is not None

        # Check imports
        imported_mods = {imp.module for imp in visitor.imports}
        assert "google" in imported_mods or "google.genai" in imported_mods
        assert "openai" in imported_mods

        # Check client inits
        init_vars = {init.variable_name: init for init in visitor.client_inits}
        assert "gemini_client" in init_vars
        assert init_vars["gemini_client"].class_name == "Client"
        assert init_vars["gemini_client"].provider_id == "google_gemini"

        assert "openai_client" in init_vars
        assert init_vars["openai_client"].class_name == "OpenAI"
        assert init_vars["openai_client"].provider_id == "openai"
        assert init_vars["openai_client"].base_url == "https://api.openai.com/v1"

    def test_api_calls_detection_and_line_accuracy(self) -> None:
        visitor = PythonAstScanner.scan_file(
            SAMPLE_REPO_PATH, SAMPLE_REPO_PATH / "src" / "ai_service.py"
        )
        assert visitor is not None

        call_ops = {c.operation for c in visitor.calls}
        assert "Client.models.generate_content" in call_ops
        assert "OpenAI.chat.completions.create" in call_ops

        for c in visitor.calls:
            assert c.line > 0
            assert c.confidence == ConfidenceLevel.CONFIRMED

    def test_direct_http_calls_with_constant_resolution(self) -> None:
        visitor = PythonAstScanner.scan_file(
            SAMPLE_REPO_PATH, SAMPLE_REPO_PATH / "src" / "billing_service.py"
        )
        assert visitor is not None

        http_calls = [c for c in visitor.calls if c.evidence_type == EvidenceType.HTTP_CALL]
        assert len(http_calls) >= 2

        methods = {c.method for c in http_calls}
        assert "POST" in methods
        assert "GET" in methods

        # Verify that STRIPE_BASE constant was resolved in f-string
        urls = {c.path for c in http_calls}
        assert "https://api.stripe.com/v1/payment_intents" in urls
        assert "https://api.stripe.com/v1/customers" in urls

        # All resolved Stripe calls should attribute provider
        for c in http_calls:
            assert c.provider_id == "stripe"
            assert c.confidence in (ConfidenceLevel.CONFIRMED, ConfidenceLevel.STRONG)

    def test_ambiguous_dynamic_url_preserves_uncertainty(self) -> None:
        visitor = PythonAstScanner.scan_file(
            SAMPLE_REPO_PATH, SAMPLE_REPO_PATH / "src" / "dynamic_service.py"
        )
        assert visitor is not None

        http_calls = [c for c in visitor.calls if c.evidence_type == EvidenceType.HTTP_CALL]
        assert len(http_calls) == 1
        finding = http_calls[0]

        assert finding.method == "GET"
        assert finding.path == UncertaintyState.AMBIGUOUS.value
        assert finding.provider_id is None
        assert finding.confidence == ConfidenceLevel.UNKNOWN

    def test_file_with_no_api_usage(self) -> None:
        visitor = PythonAstScanner.scan_file(
            SAMPLE_REPO_PATH, SAMPLE_REPO_PATH / "src" / "internal_utils.py"
        )
        assert visitor is not None
        assert len(visitor.client_inits) == 0
        assert len(visitor.calls) == 0


# =========================================================================
# LAYER 4: Attribution & Confidence Engine Tests
# =========================================================================
class TestAttributionAndConfidence:
    """Tests for package mapping and confidence scoring rules."""

    def test_package_attribute_mapping(self) -> None:
        assert attribute_package_name("google-genai") == "google_gemini"
        assert attribute_package_name("openai") == "openai"
        assert attribute_package_name("stripe") == "stripe"
        assert attribute_package_name("anthropic") == "anthropic"
        assert attribute_package_name("pygithub") == "github"
        assert attribute_package_name("fastapi") is None

    def test_url_attribute_mapping(self) -> None:
        assert attribute_url("https://generativelanguage.googleapis.com/v1beta") == "google_gemini"
        assert attribute_url("https://api.openai.com/v1/chat/completions") == "openai"
        assert attribute_url("https://api.stripe.com/v1/charges") == "stripe"
        assert attribute_url("https://api.github.com/repos") == "github"
        assert attribute_url("https://unrelated-domain.org/api") is None

    def test_compute_confidence_rules(self) -> None:
        # Candidate only: manifest or import without calls
        assert (
            compute_confidence(
                has_manifest=True,
                has_import=False,
                has_client_init=False,
                has_api_call=False,
                has_known_url=False,
            )
            == ConfidenceLevel.CANDIDATE
        )
        assert (
            compute_confidence(
                has_manifest=False,
                has_import=True,
                has_client_init=False,
                has_api_call=False,
                has_known_url=False,
            )
            == ConfidenceLevel.CANDIDATE
        )

        # Strong: client init alone or import + call
        assert (
            compute_confidence(
                has_manifest=True,
                has_import=True,
                has_client_init=True,
                has_api_call=False,
                has_known_url=False,
            )
            == ConfidenceLevel.STRONG
        )

        # Confirmed: client init + api call
        assert (
            compute_confidence(
                has_manifest=True,
                has_import=True,
                has_client_init=True,
                has_api_call=True,
                has_known_url=False,
            )
            == ConfidenceLevel.CONFIRMED
        )

        # Confirmed: API call + known host URL
        assert (
            compute_confidence(
                has_manifest=False,
                has_import=False,
                has_client_init=False,
                has_api_call=True,
                has_known_url=True,
            )
            == ConfidenceLevel.CONFIRMED
        )

    def test_package_installed_without_code_usage_is_candidate_only(self) -> None:
        engine = DiscoveryEngine()
        inventory = engine.discover(SAMPLE_REPO_PATH)

        dep_map = {d.provider: d for d in inventory.dependencies}
        assert "anthropic" in dep_map
        anthropic_dep = dep_map["anthropic"]

        # MUST be candidate, NEVER confirmed without code evidence
        assert anthropic_dep.confidence == ConfidenceLevel.CANDIDATE
        assert len(anthropic_dep.usages) == 1
        assert anthropic_dep.usages[0].evidence_type == EvidenceType.MANIFEST

    def test_confirmed_dependencies_in_sample_repo(self) -> None:
        engine = DiscoveryEngine()
        inventory = engine.discover(SAMPLE_REPO_PATH)

        dep_map = {d.provider: d for d in inventory.dependencies}
        assert dep_map["google_gemini"].confidence == ConfidenceLevel.CONFIRMED
        assert dep_map["openai"].confidence == ConfidenceLevel.CONFIRMED
        assert dep_map["stripe"].confidence == ConfidenceLevel.CONFIRMED


# =========================================================================
# SECURITY & SANITIZATION TESTS
# =========================================================================
class TestEvidenceSafetyAndSanitization:
    """Tests ensuring secrets are never persisted or exposed in findings."""

    def test_sanitize_code_snippet(self) -> None:
        assert (
            sanitize_code_snippet("api_key = 'AIzaSyA_TEST_KEY_VALUE_123456789012345'")
            == "api_key = '[REDACTED]'"
        )
        assert (
            sanitize_code_snippet("client = OpenAI(api_key='sk-1234567890abcdef1234567890abcdef')")
            == "client = OpenAI(api_key='[REDACTED]')"
        )
        assert (
            sanitize_code_snippet("raw_token = 'sk-1234567890abcdef1234567890abcdef'")
            == "raw_token = 'sk-[REDACTED]'"
        )
        auth_header = "{'Authorization': 'Bearer test_token_long_secret_123'}"
        assert (
            sanitize_code_snippet(f"headers = {auth_header}")
            == "headers = {'Authorization': 'Bearer [REDACTED]'}"
        )

    def test_sanitize_url(self) -> None:
        assert (
            sanitize_url("https://api.example.com/v1?key=AIzaSyA123456789012345678901234567890")
            == "https://api.example.com/v1?key=[REDACTED]"
        )
        assert (
            sanitize_url("https://user:password123@api.example.com/v1")
            == "https://[REDACTED]@api.example.com/v1"
        )

    def test_no_raw_secrets_in_discovered_inventory(self) -> None:
        engine = DiscoveryEngine()
        inventory = engine.discover(SAMPLE_REPO_PATH)
        dump = inventory.model_dump_json()

        # Raw secrets from sample repo must NOT be present
        assert "AIzaSyB123456789012345678901234567890" not in dump
        assert "sk-1234567890abcdef1234567890abcdef" not in dump
        assert "sk-test_98765432101234567890" not in dump


# =========================================================================
# PATH VALIDATION & FAULT TOLERANCE TESTS
# =========================================================================
class TestPathValidationAndFaultTolerance:
    """Tests for path safety, excluded directories, binary files, and syntax errors."""

    def test_validate_repository_path(self) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            validate_repository_path("nonexistent_directory_xyz")

        with tempfile.NamedTemporaryFile() as tf:
            with pytest.raises(ValueError, match="not a directory"):
                validate_repository_path(tf.name)

    def test_safe_source_discovery_skips_binaries_and_caches(self) -> None:
        files = list(discover_source_files(MALFORMED_REPO_PATH))
        file_names = [f.name for f in files]

        assert "valid.py" in file_names
        assert "broken.py" in file_names
        # data.bin must be skipped
        assert "data.bin" not in file_names

    def test_malformed_syntax_does_not_crash_discovery(self) -> None:
        engine = DiscoveryEngine()
        inventory = engine.discover(MALFORMED_REPO_PATH)

        # Must record the scan error without failing the scan
        assert inventory.metadata.get("scan_errors") == 1
        assert inventory.metadata.get("files_scanned") == 2

        # The valid file in the same repository must still be discovered
        providers = {d.provider for d in inventory.dependencies}
        assert "openai" in providers


# =========================================================================
# LEVEL 2: REAL-WORLD REPOSITORY VALIDATION
# =========================================================================
class TestRealRepoValidation:
    """Level 2 validation against real-world open source repository."""

    def test_real_repo_openai_discovery(self) -> None:
        """Verify static discovery on official openai-quickstart-python repository."""
        if not REAL_REPO_PATH.exists():
            pytest.skip("Real repository fixture not present")

        engine = DiscoveryEngine()
        inventory = engine.discover(REAL_REPO_PATH)

        dep_map = {d.provider: d for d in inventory.dependencies}
        assert "openai" in dep_map
        openai_dep = dep_map["openai"]

        # Real repo imports openai, constructs OpenAI(), and calls chat.completions.create
        assert openai_dep.confidence == ConfidenceLevel.CONFIRMED
        assert openai_dep.base_url == "https://api.openai.com/v1"
        assert len(openai_dep.usages) > 10

        # Verify evidence types present
        ev_types = {u.evidence_type for u in openai_dep.usages}
        assert EvidenceType.MANIFEST in ev_types
        assert EvidenceType.SDK_IMPORT in ev_types
        assert EvidenceType.AST_CALL in ev_types

        # Verify line numbers and files
        for u in openai_dep.usages:
            assert u.line >= 1
            assert (REAL_REPO_PATH / u.file).exists()


# =========================================================================
# UNREGISTERED PROVIDER AGNOSTIC DISCOVERY TESTS
# =========================================================================
# =========================================================================
# UNREGISTERED PROVIDER AGNOSTIC DISCOVERY TESTS
# =========================================================================
class TestUnregisteredProviderDiscovery:
    """Verify that discovery engine is provider-agnostic and preserves unregistered APIs."""

    def test_unregistered_manifest_dependency_is_candidate(self) -> None:
        """Unregistered package declared in requirements.txt must be preserved as CANDIDATE."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            req = tmp_path / "requirements.txt"
            req.write_text("resend>=1.2.0\n", encoding="utf-8")

            engine = DiscoveryEngine()
            inventory = engine.discover(tmp_path)

            dep_map = {d.provider: d for d in inventory.dependencies}
            assert "package:resend" in dep_map
            dep = dep_map["package:resend"]

            # Must be candidate only; manifest alone is never confirmed
            assert dep.confidence == ConfidenceLevel.CANDIDATE
            assert dep.sdk == "resend"
            assert len(dep.usages) == 1

            u = dep.usages[0]
            assert u.evidence_type == EvidenceType.MANIFEST
            assert u.file == "requirements.txt"
            assert u.line == 1
            assert "resend" in (u.context_snippet or "")
            assert "1.2.0" in (u.context_snippet or "")

    def test_unregistered_import_is_candidate(self) -> None:
        """Unregistered third-party import must be attributed to package:<root> as CANDIDATE."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create a local project file to verify exclusion
            local_mod = tmp_path / "my_local_helper.py"
            local_mod.write_text("def helper(): pass\n", encoding="utf-8")

            app = tmp_path / "app.py"
            app.write_text(
                (
                    "import os\n"
                    "import sys\n"
                    "import my_local_helper\n"
                    "import resend\n"
                    "from sendgrid.helpers.mail import Mail\n"
                ),
                encoding="utf-8",
            )

            engine = DiscoveryEngine()
            inventory = engine.discover(tmp_path)

            dep_map = {d.provider: d for d in inventory.dependencies}

            # Standard library and local imports MUST be excluded
            assert "package:os" not in dep_map
            assert "package:sys" not in dep_map
            assert "package:my_local_helper" not in dep_map

            # Unregistered third-party imports must be preserved as candidates
            assert "package:resend" in dep_map
            assert dep_map["package:resend"].confidence == ConfidenceLevel.CANDIDATE
            assert dep_map["package:resend"].usages[0].evidence_type == EvidenceType.SDK_IMPORT
            assert dep_map["package:resend"].usages[0].line == 4

            assert "package:sendgrid" in dep_map
            assert dep_map["package:sendgrid"].confidence == ConfidenceLevel.CANDIDATE
            assert dep_map["package:sendgrid"].usages[0].evidence_type == EvidenceType.SDK_IMPORT
            assert dep_map["package:sendgrid"].usages[0].line == 5

    def test_unregistered_client_construction(self) -> None:
        """Unregistered client constructor must be preserved with STRONG confidence."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            app = tmp_path / "app.py"
            app.write_text(
                (
                    "from resend import Resend\n\n"
                    "client = Resend(base_url='https://api.resend.com')\n"
                ),
                encoding="utf-8",
            )

            engine = DiscoveryEngine()
            inventory = engine.discover(tmp_path)

            dep_map = {d.provider: d for d in inventory.dependencies}
            assert "package:resend" in dep_map
            dep = dep_map["package:resend"]

            # Client construction without call evidence is STRONG
            assert dep.confidence == ConfidenceLevel.STRONG
            assert dep.base_url == "https://api.resend.com"
            assert dep.sdk == "resend"

            ops = {u.operation for u in dep.usages}
            assert "Resend.__init__" in ops

    def test_unregistered_client_construction_dot_notation(self) -> None:
        """Unregistered client constructor via module dot-notation e.g. resend.Client()."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            app = tmp_path / "app.py"
            app.write_text(
                ("import resend\n\nclient = resend.Client()\n"),
                encoding="utf-8",
            )

            engine = DiscoveryEngine()
            inventory = engine.discover(tmp_path)

            dep_map = {d.provider: d for d in inventory.dependencies}
            assert "package:resend" in dep_map
            dep = dep_map["package:resend"]

            # Attributed using imported module, confidence STRONG
            assert dep.confidence == ConfidenceLevel.STRONG
            ops = {u.operation for u in dep.usages}
            assert "Client.__init__" in ops

    def test_unregistered_client_api_call_is_confirmed(self) -> None:
        """Unregistered SDK with client construction + method call must be CONFIRMED."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            req = tmp_path / "requirements.txt"
            req.write_text("custom-ai-sdk>=2.0.0\n", encoding="utf-8")

            app = tmp_path / "app.py"
            app.write_text(
                (
                    "from custom_ai_sdk import CustomAI\n\n"
                    "client = CustomAI(base_url='https://api.custom-ai.org/v1')\n"
                    "result = client.generate_text('hello')\n"
                ),
                encoding="utf-8",
            )

            engine = DiscoveryEngine()
            inventory = engine.discover(tmp_path)

            dep_map = {d.provider: d for d in inventory.dependencies}
            assert "package:custom_ai_sdk" in dep_map
            dep = dep_map["package:custom_ai_sdk"]

            # Must be CONFIRMED with exact evidence preserved
            assert dep.confidence == ConfidenceLevel.CONFIRMED
            assert dep.base_url == "https://api.custom-ai.org/v1"
            assert dep.sdk == "custom-ai-sdk"

            ev_types = {u.evidence_type for u in dep.usages}
            assert EvidenceType.MANIFEST in ev_types
            assert EvidenceType.SDK_IMPORT in ev_types
            assert EvidenceType.AST_CALL in ev_types

            # Verify call correlation
            ops = [u.operation for u in dep.usages if u.evidence_type == EvidenceType.AST_CALL]
            assert "CustomAI.__init__" in ops
            assert "CustomAI.generate_text" in ops

    def test_generic_client_without_provider_evidence_remains_unknown(self) -> None:
        """Generic Client() with no provider evidence must remain UNKNOWN, never guessed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            app = tmp_path / "generic_service.py"
            app.write_text(
                (
                    "# Generic Client instantiation with no import evidence\n"
                    "client = Client()\n"
                    "client.do_something()\n"
                    "api = API()\n"
                    "api.call()\n"
                ),
                encoding="utf-8",
            )

            engine = DiscoveryEngine()
            inventory = engine.discover(tmp_path)

            dep_map = {d.provider: d for d in inventory.dependencies}

            # MUST NEVER guess google_gemini, openai, or any provider
            assert "google_gemini" not in dep_map
            assert "openai" not in dep_map
            assert "stripe" not in dep_map
            assert "anthropic" not in dep_map

            # Must remain UNKNOWN
            assert UncertaintyState.UNKNOWN.value in dep_map
            unknown_dep = dep_map[UncertaintyState.UNKNOWN.value]
            assert unknown_dep.confidence == ConfidenceLevel.UNKNOWN

            ops = {u.operation for u in unknown_dep.usages}
            assert "Client.__init__" in ops
            assert "Client.do_something" in ops

    def test_unknown_direct_http_host(self) -> None:
        """Direct HTTP call to unregistered endpoint must be preserved under UNKNOWN attribution."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            app = tmp_path / "payment.py"
            app.write_text(
                (
                    "import requests\n\n"
                    "def charge():\n"
                    "    return requests.post('https://api.custom-payment.net/v2/charge')\n"
                ),
                encoding="utf-8",
            )

            engine = DiscoveryEngine()
            inventory = engine.discover(tmp_path)

            dep_map = {d.provider: d for d in inventory.dependencies}
            assert UncertaintyState.UNKNOWN.value in dep_map
            unknown_dep = dep_map[UncertaintyState.UNKNOWN.value]

            # Finding must NOT be discarded
            assert len(unknown_dep.usages) >= 1
            http_usage = unknown_dep.usages[0]
            assert http_usage.evidence_type == EvidenceType.HTTP_CALL
            assert http_usage.method == "POST"
            assert http_usage.path == "https://api.custom-payment.net/v2/charge"
            assert http_usage.line == 4

    def test_ambiguous_dynamic_url(self) -> None:
        """Dynamic URL variable without static resolution must preserve AMBIGUOUS path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            app = tmp_path / "dynamic.py"
            app.write_text(
                (
                    "import requests\n\n"
                    "def fetch_dynamic(path):\n"
                    "    dynamic_url = f'https://custom-host.com/{path}'\n"
                    "    return requests.get(dynamic_url)\n"
                ),
                encoding="utf-8",
            )

            engine = DiscoveryEngine()
            inventory = engine.discover(tmp_path)

            dep_map = {d.provider: d for d in inventory.dependencies}
            assert UncertaintyState.UNKNOWN.value in dep_map
            unknown_dep = dep_map[UncertaintyState.UNKNOWN.value]

            assert len(unknown_dep.usages) >= 1
            http_usage = unknown_dep.usages[0]
            assert http_usage.method == "GET"
            assert http_usage.path == UncertaintyState.AMBIGUOUS.value
            assert http_usage.confidence == ConfidenceLevel.UNKNOWN

    def test_known_provider_regression(self) -> None:
        """Regression test ensuring known providers retain canonical IDs without package: prefix."""
        engine = DiscoveryEngine()
        inventory = engine.discover(SAMPLE_REPO_PATH)

        dep_map = {d.provider: d for d in inventory.dependencies}

        # Registered providers must use canonical IDs
        assert "google_gemini" in dep_map
        assert "openai" in dep_map
        assert "stripe" in dep_map
        assert "anthropic" in dep_map

        assert "package:google_genai" not in dep_map
        assert "package:openai" not in dep_map
        assert "package:stripe" not in dep_map

        assert dep_map["google_gemini"].confidence == ConfidenceLevel.CONFIRMED
        assert dep_map["openai"].confidence == ConfidenceLevel.CONFIRMED
        assert dep_map["stripe"].confidence == ConfidenceLevel.CONFIRMED
        assert dep_map["anthropic"].confidence == ConfidenceLevel.CANDIDATE
