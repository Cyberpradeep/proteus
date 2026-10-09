# PROTEUS

Repository-Aware API Evolution Monitoring, Impact Analysis, and Automated Repair.

## Overview

Modern software frequently depends on external third-party APIs (LLM providers, payment gateways, developer platforms). Upstream changes—such as endpoint deprecations, parameter removals, model retirement, or altered response schemas—routinely cause silent runtime failures in downstream applications.

PROTEUS inspects consumer repositories to identify external API dependencies, infers application intent, tracks upstream changes against authoritative provider sources, and verifies impact deterministically before planning automated repairs.

## Architecture Pipeline

```text
Repository
  -> API Discovery          [Implemented]
  -> Intent Profiling       [Upcoming]
  -> Resource Resolution    [Upcoming]
  -> Live Collection        [Upcoming]
  -> Snapshot Storage       [Implemented Foundation]
  -> Normalization          [Implemented Foundation]
  -> Change Detection       [Upcoming]
  -> Consumer Impact        [Upcoming]
  -> Repair Planning        [Upcoming]
  -> Verification           [Upcoming]
```

## Implementation Status

### 1. Project Foundation and Storage
* SQLite storage engine with Write-Ahead Logging (WAL) and foreign key enforcement.
* Schema supporting projects, inventories, intents, source definitions, raw snapshots, normalized contracts, and change events.
* Immutable snapshot store enforcing SHA-256 hash integrity checks upon ingestion.

### 2. Core Data Models
* Strongly typed Pydantic v2 domain models.
* First-class uncertainty modeling: `CONFIRMED`, `CANDIDATE`, `UNKNOWN`, `UNAVAILABLE`, and `NOT_OBSERVED`. States are never collapsed into artificial defaults.

### 3. Static API Discovery Engine
* **Manifest Scanning**: Parses `pyproject.toml`, `requirements.txt`, and `package.json` to identify declared dependencies.
* **Python AST Analysis**: Traverses Python syntax trees to locate imports, client constructors (e.g., `OpenAI()`, `genai.Client()`), SDK method invocations, and call-site line numbers.
* **HTTP Call Resolution**: Detects direct HTTP requests (`httpx`, `requests`, `aiohttp`, `fetch`), resolves constant URLs, and tags dynamic or unresolved targets as ambiguous.
* **Attribution and Confidence Scoring**: Categorizes findings into confirmed usage, candidate declarations (imported/declared but uncalled), and unresolved endpoints. Supports both registered providers (OpenAI, Google Gemini, Stripe, Anthropic, GitHub) and dynamic/unregistered providers.
* **Evidence Sanitization**: Automatically scrubs API keys, bearer tokens, authorization headers, and query credentials from evidence snippets before storage.

### 4. CLI Interface
* `proteus scan <path>`: Scans a repository and outputs a structured human-readable report or JSON payload (`--json`).
* `proteus sources list`: Lists registered API monitoring sources.
* `proteus snapshots list`: Inspects ingested raw snapshots.
* `proteus changes list`: Displays detected API change events.
* `proteus version`: Displays version information.

## Getting Started

### Prerequisites
* Python 3.11 or higher
* `uv` or `pip`

### Installation

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/Cyberpradeep/proteus.git
cd proteus

python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On Linux/macOS:
source .venv/bin/activate

pip install -e ".[dev]"
```

## CLI Usage

### Scan a Repository

Scan a target repository to identify API dependencies and extract evidence:

```bash
# Human-readable console report
proteus scan /path/to/target-repo

# Machine-readable JSON output
proteus scan /path/to/target-repo --json
```

Example scan output:

```text
====================================================================
 PROTEUS API DISCOVERY REPORT
====================================================================
Target Repository : /workspace/sample_repo
Discovered At     : 2026-10-09T11:29:30.562751+00:00
Files Scanned     : 4
Scan Errors       : 0
Total APIs Found  : 6
Total Usages      : 13
--------------------------------------------------------------------

[CONFIRMED API DEPENDENCIES]
  * google_gemini (SDK: google-genai) [Base: https://generativelanguage.googleapis.com] - 3 usage(s):
    - pyproject.toml:1 [MANIFEST] declare_dependency
    - src/ai_service.py:7 [AST_CALL] Client.__init__
    - src/ai_service.py:16 [AST_CALL] Client.models.generate_content
  * openai (SDK: openai) [Base: https://api.openai.com/v1] - 4 usage(s):
    - pyproject.toml:2 [MANIFEST] declare_dependency
    - src/ai_service.py:4 [SDK_IMPORT] import
    - src/ai_service.py:8 [AST_CALL] OpenAI.__init__
    - src/ai_service.py:25 [AST_CALL] OpenAI.chat.completions.create
  * stripe (SDK: stripe) [Base: https://api.stripe.com] - 3 usage(s):
    - pyproject.toml:3 [MANIFEST] declare_dependency
    - src/billing_service.py:14 [HTTP_CALL] client.post path=https://api.stripe.com/v1/payment_intents
    - src/billing_service.py:25 [HTTP_CALL] requests.get path=https://api.stripe.com/v1/customers

[CANDIDATE DEPENDENCIES (Declared / Imported Only - No Calls Observed)]
  * anthropic (SDK: anthropic) - 1 declaration(s):
    - pyproject.toml:4 [MANIFEST] anthropic (project.dependencies)

[AMBIGUOUS / UNKNOWN HTTP USAGES (Unresolved Host or Dynamic Endpoint)]
  * UNKNOWN - 1 usage(s):
    - src/dynamic_service.py:9 [HTTP_CALL] GET AMBIGUOUS
====================================================================
```

### Inspect Database Records

```bash
# List monitored sources
proteus sources list

# List snapshots
proteus snapshots list

# View change events
proteus changes list
```

## Running Tests

Execute the test suite using pytest:

```bash
pytest
```

All 67 unit and integration tests cover models, storage persistence, AST traversal, HTTP detection, attribution rules, credential redaction, and CLI behavior.

## Core Design Rules

* **Deterministic by Default**: Uses parsers, AST visitors, HTTP clients, and cryptographic hashes instead of non-deterministic heuristics.
* **Traceable Evidence**: Every finding references its source file, line number, and sanitized snippet.
* **Explicit Uncertainty**: Unknown or unobserved items remain explicitly marked rather than coerced to false values.
* **Security Boundaries**: Repository secrets, API tokens, and `.env` files are stripped and never exposed.
