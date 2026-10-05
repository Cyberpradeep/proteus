# TECHNICAL DESIGN DOCUMENT


## PROTEUS

Repository-Aware API Evolution Monitoring, Impact Analysis and Automated Repair

A system design for discovering API dependencies, maintaining current provider state, detecting consumer-relevant changes, and guiding safe adaptation.


# Document Control


# How to Read This Document

This document defines the technical baseline for PROTEUS before implementation begins. It separates the problem domain from the implementation tools so that individual technologies can be replaced without redesigning the whole system. The design starts from the project study and turns the conceptual pipeline into modules, interfaces, data models, security rules, testing expectations, and a staged development path.


# Design Principles

• Evidence first: Every important assessment must point back to a source, snapshot, static usage result, or runtime observation.

• Deterministic by default: Do not use an LLM for tasks that can be solved reliably with parsers, rules, hashes, diffs, or tests.

• Provider agnostic: Provider-specific details live in adapters and source definitions; the internal model stays common.

• Least privilege: Scanning and monitoring should use the minimum credentials, network access, and repository permissions needed.

• Fail independently: A failed provider fetch or LLM call should not stop analysis of unrelated APIs.

• Human review when uncertain: The system should be able to say that it cannot safely determine the answer.


# 1. System Overview

PROTEUS is a software-maintenance system for applications that depend on external APIs. The system first discovers the APIs a repository actually uses. It then examines the surrounding code to understand the purpose of each usage and determine which live API properties matter. For those properties, PROTEUS resolves authoritative sources, collects current state, stores historical snapshots, and compares states to identify relevant API evolution. Later components use the detected change to locate affected consumer code, plan a repair, and verify the result.


## 1.1 System Boundary

- Inside PROTEUS: repository analysis, API dependency modeling, intent profiling, source resolution, collection, snapshotting, normalization, change detection, impact analysis, repair planning, and verification orchestration.

- Outside PROTEUS: ownership of third-party APIs, provider-side change control, bypassing authentication or security controls, and unsupervised modification of production systems.


## 1.2 Primary Use Case

A developer supplies a repository. PROTEUS identifies that the application uses an external provider, for example Gemini, Stripe, GitHub, or another API. It records the specific usage, determines what current information matters to that usage, retrieves current provider evidence, and watches for changes. When a relevant change appears, PROTEUS reports the evidence and—after the impact and repair stages are implemented—can generate a reviewable adaptation.


## 1.3 End-to-End Flow

Fig. 1. High-level PROTEUS architecture and evidence flow.


# 2. Requirements and Scope


## 2.1 Functional Requirements


## 2.2 Non-Functional Requirements


## 2.3 Non-Goals

- Universal support for every programming language in the first release.

- Autonomous production changes without review.

- Bypassing CAPTCHA, MFA, bot protection, rate limits, or provider access controls.

- Treating an LLM response as authoritative live API truth.

- Replacing provider monitoring platforms or API gateways.


# 3. Component Architecture


## 3.1 Module Interfaces


# 4. Repository API Discovery

Discovery is the first operational component because all later monitoring depends on knowing which external APIs the application actually uses.


## 4.1 Discovery Evidence Sources


## 4.2 Discovery Pipeline

A. Candidate scan: Collect cheap signals first: package names, imports, URLs, HTTP library calls, and configuration values.

B. Structural confirmation: Use AST or Tree-sitter to confirm that a candidate corresponds to a real call site rather than a comment, string, or documentation example.

C. Identity resolution: Merge evidence such as an SDK import and a base URL into one provider/dependency record.

D. Usage extraction: Record the operation, method/path where known, source file, line, symbol, and source of evidence.

E. Optional runtime confirmation: In a controlled environment, observe actual external destinations and update confidence.


## 4.3 Example Output


# 5. Intent Profiling and Resource Resolution


## 5.1 Why Intent Exists

A provider may expose hundreds of endpoints or models, while a consumer may depend on only a small subset. PROTEUS therefore asks what the specific application is doing with the API and which live properties can affect that use. This reduces unnecessary monitoring and helps distinguish a provider-wide change from a consumer-relevant change.


## 5.2 LLM Responsibility


## 5.3 Resource Resolution

The Resource Resolver converts a monitoring intent into a source plan. A source can be a live provider resource, OpenAPI/Swagger document, changelog, deprecation page, migration guide, SDK registry, or authorized runtime telemetry endpoint. Known providers should be described in a provider registry; unknown providers can be resolved through assisted discovery followed by deterministic verification.


# 6. Live Monitoring and Snapshot Storage


## 6.1 Collection Strategy

Fig. 2. Monitoring and semantic comparison cycle.

- Use event-driven mechanisms such as webhooks or repository events when they are available and trustworthy.

- Use polling when no suitable event exists. Poll intervals are source-specific rather than globally fixed.

- Use HTTP cache validators such as ETag and Last-Modified where the source supports them.

- Record failures as source-health events and continue other scheduled jobs.


## 6.2 Initial Storage Model


## 6.3 Raw vs Normalized Data

- Raw snapshot = exact fetched evidence plus retrieval metadata.

- Normalized contract = canonical provider-neutral structure used by later modules.

- Change event = semantic difference between normalized states.


# 7. Normalization and Change Detection


## 7.1 Normalization

Normalization removes provider-specific formatting differences so that the change engine compares meaning rather than raw document text. A normalized contract may contain endpoints, operations, parameters, request schemas, response schemas, lifecycle state, versions, and capability metadata.


## 7.2 Change Categories


## 7.3 Semantic Comparison


# 8. Consumer Impact Analysis


## 8.1 Mapping Provider Changes to Code

The Impact Analyzer answers a narrower question than the Change Engine: does this repository actually depend on the changed capability? It starts with the API usage graph produced during discovery and then applies structural source analysis to confirm exact call sites.


## 8.2 Impact Result


# 9. Repair Planning and Verification


## 9.1 Repair Decision

PROTEUS should classify a repair before editing code. Simple transformations should use deterministic rules; ambiguous transformations can be assisted by an LLM; changes that require business judgment should stop for human review.


## 9.2 Verification Levels

1. Baseline: Run the original project enough to know whether existing build/tests already fail.

2. Static checks: Run formatting, linting, type checking, and dependency validation.

3. Tests: Run project unit/integration tests and compare against the baseline.

4. Replay: Later, replay representative requests/interactions in a controlled environment.

5. Behavior assertions: Check that intended application-level outcomes are preserved, not only that code compiles.


# 10. Security, Reliability and Privacy


## 10.1 Security Controls


## 10.2 Reliability Rules

- Each monitoring job has a timeout and bounded retries with backoff.

- A failed source is marked unhealthy without blocking unrelated providers.

- Partial results are explicit; missing data is never silently treated as zero or unchanged.

- Every asynchronous job has an idempotent job key so retries do not create duplicate snapshots.

- All major state changes are logged with correlation IDs.


# 11. Software Engineering and Development Standards


## 11.1 Repository Structure


## 11.2 Team Development Rules

- Use feature branches and pull requests; do not develop directly on main.

- Keep commits small and focused on one change.

- Every new module includes unit tests and a minimal usage example.

- Keep provider-specific logic in provider adapters/registry data rather than spreading it through core modules.

- Run formatting, linting, and tests before merge.

- Document architectural decisions that affect module boundaries or data contracts.


## 11.3 Testing Pyramid


# 12. Technology Baseline


# 13. Operational Observability


## 13.1 Developer-Facing CLI

The CLI is the initial interface because it keeps development focused on the core engine. A web dashboard can be added later on top of the same service interfaces.


# 14. Development Path


## 14.1 Recommended First Vertical Slice

Do not build every provider or every language first. Start with one representative repository and two external APIs. Make the complete path work from repository discovery through a controlled change event before adding more providers or sophisticated repair logic.


# 15. Evaluation Plan


## 15.1 What to Measure


## 15.2 Evaluation Dataset Strategy

Use controlled repositories and version pairs for which the expected API changes are known. Include endpoint removal, parameter requiredness, response-field changes, deprecations, and at least one case where the schema is unchanged but observed behavior differs. Keep a ground-truth record of the injected or known change for comparison.


# 16. Key Risks and Mitigations


# 17. Design Conclusion

The technical design establishes PROTEUS as a modular evidence-backed maintenance system rather than a monolithic AI agent. The first implementation should prove the deterministic backbone: discover external API dependencies, understand the consumer intent, resolve verified live sources, collect and store current state, and detect meaningful changes. Consumer impact, repair, and behavioral verification can then be layered on without changing the core data contracts.


# 18. References

[1] P. Schmiedmayer, A. Bauer, and B. Bruegge, “Reducing the Impact of Breaking Changes to Web Service Clients During Web API Evolution,” IEEE/ACM MOBILESoft, 2023, DOI: 10.1109/MOBILSoft59058.2023.00008.

[2] A. Lercher et al., “Microservice API Evolution in Practice: A Study on Strategies and Challenges,” Journal of Systems and Software, 2024, DOI: 10.1016/j.jss.2024.112110.

[3] S. Serbout and C. Pautasso, “How Many Web APIs Evolve Following Semantic Versioning?,” ICWE 2024, DOI: 10.1007/978-3-031-62362-2_25.

[4] J. Yasmin, Y. Tian, and J. Yang, “A First Look at the Deprecation of RESTful APIs: An Empirical Study,” IEEE ICSME, 2020, DOI: 10.1109/ICSME46990.2020.00024.

[5] L. Fruntke and J. Krinke, “Automatically Fixing Dependency Breaking Changes,” Proceedings of the ACM on Software Engineering, FSE, 2025, DOI: 10.1145/3729366.

[6] OpenAPI Initiative, “OpenAPI Specification,” official specification documentation.

[7] OpenTelemetry, “OpenTelemetry Specification,” official specification documentation.

[8] oasdiff project, “OpenAPI diff and breaking-change analysis,” project documentation.

[9] Tree-sitter, “Tree-sitter Documentation,” parser and syntax-tree documentation.

[10] Pydantic Documentation, data validation and typed model documentation.

[11] Python Documentation, sqlite3 module documentation.

[12] APScheduler Documentation, scheduling and job execution documentation.

PROTEUS  •  Technical Design Baseline  •  Version 0.1


# Tables


## Table 1

| MUTHAYAMMAL ENGINEERING COLLEGE Department of CSE (Cyber Security)  •  B.E. Cyber Security  •  Final Year  •  Batch 2023–2027 Project Team Poovarasan S  (23CY038) Sachin P  (23CY045) Malleshwaran P  (23CY030) Pradeep S  (23CY039) |

| --- |


## Table 2

| DESIGN STATUS Version 0.1 • Architecture baseline for development planning. Implementation choices can be refined after the first working prototype. |

| --- |


## Table 3

| Item | Value |

| --- | --- |

| Document | PROTEUS Technical Design Document |

| System | PROTEUS |

| Document version | 0.1 |

| Audience | Project team, guide, reviewers, developers |

| Primary base paper | Schmiedmayer, Bauer and Bruegge, MOBILESoft 2023 |

| Development approach | Incremental, modular, test-driven |

| Initial persistence | SQLite |

| Initial service style | Python package + CLI; service layer can be added later |


## Table 4

| CORE ENGINEERING RULE The system should use the LLM for interpretation where useful, but rely on deterministic collection, normalization, comparison and verification for facts and evidence. |

| --- |


## Table 5

| ID | Requirement | Description |

| --- | --- | --- |

| FR-01 | Repository intake | Accept a repository path and identify the languages, manifests, configuration files, and candidate API dependencies. |

| FR-02 | API discovery | Discover APIs from package manifests, SDK imports, direct HTTP calls, configuration, and controlled runtime evidence. |

| FR-03 | Intent profiling | Produce a structured profile describing why a discovered API is used and which capabilities/properties matter. |

| FR-04 | Source resolution | Maintain verified source definitions for live provider resources, contracts, changelogs, deprecations, and migration information. |

| FR-05 | Monitoring | Fetch current source state by polling when needed and by event-driven mechanisms when supported. |

| FR-06 | Snapshotting | Store timestamped raw and normalized snapshots with hashes and retrieval metadata. |

| FR-07 | Change detection | Emit structured change events when normalized provider state changes. |

| FR-08 | Impact analysis | Map changed provider capabilities to consumer call sites and assumptions. |

| FR-09 | Repair planning | Classify a migration as deterministic, LLM-assisted, or manual-review. |

| FR-10 | Verification | Run static checks, tests, and later representative API replay before a repair is considered verified. |


## Table 6

| Property | Requirement |

| --- | --- |

| Reliability | One provider failure must not stop unrelated monitoring jobs. |

| Traceability | Every change event must retain source, timestamp, snapshot and reasoning metadata. |

| Security | Secrets must stay outside source control and must not be included in LLM prompts. |

| Modularity | Each component must expose a small input/output contract and be independently testable. |

| Reproducibility | A monitoring result must be reconstructable from stored snapshots and configuration. |

| Maintainability | Provider-specific code should be isolated behind adapters and registry data. |

| Cost control | LLM calls should be bounded and only used where they add reasoning value. |


## Table 7

| Component | Input | Output | Primary responsibility |

| --- | --- | --- | --- |

| Repository Analyzer | Repository path | ApiInventory | Static discovery of API candidates and usage locations. |

| Intent Profiler | Relevant code context + ApiUsage | MonitoringIntent | LLM-assisted interpretation of application purpose. |

| Resource Resolver | MonitoringIntent + provider identity | SourceRegistry | Maps needs to verified authoritative sources. |

| Collector | SourceDefinition | RawSnapshot | Fetches and validates current source state. |

| Snapshot Store | RawSnapshot | Snapshot history | Persists evidence and metadata. |

| Normalizer | RawSnapshot | NormalizedContract | Converts provider-specific data to a common representation. |

| Change Engine | Old + New NormalizedContract | ChangeEvent[] | Semantic comparison and classification. |

| Impact Analyzer | ChangeEvent + consumer model | ImpactResult | Finds affected call sites and assumptions. |

| Repair Planner | ImpactResult + migration evidence | RepairPlan | Chooses deterministic, LLM-assisted, or manual route. |

| Verifier | Repair + test environment | VerificationReport | Build/test/replay checks and evidence aggregation. |


## Table 8

| ApiInventory discover(repository_path) MonitoringIntent profile(api_usage, code_context) SourceRegistry resolve(monitoring_intent) RawSnapshot collect(source_definition) NormalizedContract normalize(raw_snapshot) list[ChangeEvent] compare(previous, current) ImpactResult analyze(change_event, consumer_model) RepairPlan plan(impact_result, migration_evidence) VerificationReport verify(repair, test_environment) |

| --- |


## Table 9

| INTERFACE RULE Modules exchange typed models rather than provider-specific dictionaries. This keeps the architecture stable when an implementation library or provider adapter changes. |

| --- |


## Table 10

| Evidence source | What we extract | Confidence role |

| --- | --- | --- |

| Dependency manifests | Package names, versions, registries | Candidate |

| SDK imports / client construction | Provider SDK symbols and client objects | Strong |

| Direct HTTP calls | Hosts, paths, methods, request construction | Strong |

| Configuration | Base URLs, service identifiers, environment configuration | Supporting |

| Controlled runtime traces | Actual external destinations observed during authorized execution | Confirmation |


## Table 11

| ApiDependency   provider: google_gemini   base_url: https://generativelanguage.googleapis.com   sdk: google-genai   usages:     - operation: generate_content       file: src/ai/chat.py       line: 42       evidence: sdk_import + ast_call |

| --- |


## Table 12

| Task | LLM role | Deterministic follow-up |

| --- | --- | --- |

| Understand purpose | Infer application purpose from relevant code context. | Store a typed monitoring intent profile. |

| Identify important properties | Suggest which model, request, response, lifecycle or capability properties matter. | Map each property to a source definition. |

| Interpret ambiguous prose | Summarize migration wording or possible mappings. | Require source evidence and validation before use. |

| Suggest repair mapping later | Propose a transformation when rules are insufficient. | Validate AST, types, builds and tests. |


## Table 13

| TRUST BOUNDARY The LLM proposes interpretations. The provider API, official documentation, versioned specification, runtime observation, or test result supplies the evidence. |

| --- |


## Table 14

| SourceDefinition   provider: google_gemini   source_type: live_resource   purpose: model_availability   location: official provider endpoint   collection: http   freshness_policy: 6h   authority: verified |

| --- |


## Table 15

| Entity | Key fields | Purpose |

| --- | --- | --- |

| projects | id, name, repository_path | Track analyzed repositories. |

| apis | id, project_id, provider, base_url, sdk | Store discovered external API dependencies. |

| api_usages | api_id, method, path, file, line, symbol | Store specific consumer usage. |

| sources | api_id, type, location, authority, policy | Define where current truth comes from. |

| snapshots | source_id, fetched_at, hash, status, raw_ref | Preserve exact evidence and retrieval state. |

| contracts | snapshot_id, normalized_json | Provider-neutral representation. |

| changes | old_snapshot, new_snapshot, type, severity | Record semantic evolution. |

| jobs | source_id, scheduled_for, status, attempt_count | Track collection execution. |


## Table 16

| STORAGE RULE Never overwrite the only copy of a prior snapshot. Historical state is part of the evidence chain needed to explain why a change was detected. |

| --- |


## Table 17

| Category | Examples | Typical interpretation |

| --- | --- | --- |

| Endpoint | Added, removed, renamed | May be breaking if a consumer uses the old operation. |

| Parameter | Requiredness, type, enum, default | Can break request construction. |

| Request schema | Required property, structure | Potentially breaking. |

| Response schema | Field removed, type changed, status removed | Potentially breaking for consumers. |

| Lifecycle | Deprecated, sunset, restored | Requires migration planning; not always immediately breaking. |

| Behavioral candidate | Observed semantics differ while schema is unchanged | Requires runtime evidence and consumer analysis. |


## Table 18

| OLD CONTRACT                    NEW CONTRACT POST /payments                   POST /payments currency: optional               currency: required                   -> CHANGE EVENT <- kind: parameter_required severity: breaking evidence: old_snapshot + new_snapshot |

| --- |


## Table 19

| IMPORTANT LIMITATION Contract diffing can only prove changes represented by the contract. Behavioral drift that is not declared in the specification requires observed runtime evidence or a controlled replay. |

| --- |


## Table 20

| Usage pattern | Primary technique | Evidence |

| --- | --- | --- |

| SDK call | AST / Tree-sitter + SDK symbol mapping | Call symbol, file, line, package version |

| Direct HTTP | AST extraction + URL/path matching | Method, host, path, request body |

| Wrapped client | Call graph / symbol tracing | Wrapper function and downstream client call |

| Dynamic endpoint | Runtime observation + contextual static analysis | Observed destination + code context |

| Response assumption | Data-flow / field access analysis | Specific response property consumed by code |


## Table 21

| ImpactResult   change_id: chg_0012   affected: true   call_sites:     - file: src/payment/service.py       line: 42       symbol: create_payment   changed_element: currency   consumer_state: missing   impact: likely_breaking   evidence: ast + api_mapping |

| --- |


## Table 22

| Route | When to use | Output |

| --- | --- | --- |

| Deterministic | Exact migration rule and unambiguous call-site match. | Patch + validation evidence. |

| LLM-assisted | Migration semantics are clear enough to reason about but not directly transformable. | Structured edit plan / draft patch. |

| Human review | Business meaning is ambiguous, required values are unknown, or evidence is insufficient. | Explanation + unresolved action. |


## Table 23

| OUTCOME MODEL Every attempted repair should end as VERIFIED, DRAFT FOR REVIEW, or CANNOT SAFELY DETERMINE. |

| --- |


## Table 24

| Risk | Control |

| --- | --- |

| Secret leakage | Exclude .env secrets, tokens, cookies, and credentials from LLM context and logs. |

| SSRF during source resolution | Allow only approved schemes and verified provider domains; validate redirects. |

| Untrusted repository execution | Prefer static analysis; use isolated, authorized environments for runtime execution. |

| Excessive provider access | Use scoped credentials, rate limits, timeouts, and source-specific budgets. |

| Prompt injection in repository text | Treat repository text as untrusted data; delimit code context and do not let it change system/tool policies. |

| Corrupted evidence | Validate content types and parsed structures before normalization and storage. |


## Table 25

| proteus/   discovery/   intent/   resolver/   collector/   storage/   normalize/   diff/   impact/   repair/   verify/   models/   cli/   tests/   providers/ config/ docs/ scripts/ |

| --- |


## Table 26

| Level | What is tested | Target |

| --- | --- | --- |

| Unit | Parsers, normalizers, diff rules, models | Fast and broad coverage |

| Integration | Resolver -> collector -> storage -> normalizer | Correct module contracts |

| End-to-end | Repository -> discovery -> source -> change report | System behavior |

| Evaluation | Controlled changes across sample repositories | Research metrics and comparison |


## Table 27

| Layer | Baseline choice | Reason / role |

| --- | --- | --- |

| Language | Python | Good fit for parsing, HTTP, data processing and AI integration. |

| Dependency manager | uv | Reproducible Python environments and lockfile-based installs. |

| Repository parsing | Python AST + Tree-sitter | Precise code structure; language expansion later. |

| HTTP client | HTTPX | Sync/async HTTP collection with reusable clients. |

| Data models | Pydantic | Typed internal contracts and validation. |

| Storage | SQLite first | Simple local persistence for prototype; PostgreSQL can follow. |

| Scheduling | APScheduler or equivalent | Recurring collection jobs and job state. |

| API contract | OpenAPI | Structured provider contract where published. |

| OpenAPI diff | oasdiff or equivalent | Semantic contract comparison instead of text diff. |

| Runtime evidence | OpenTelemetry | Standardized traces/spans for authorized observation. |

| LLM | Provider abstraction; initial Z.AI/GLM option | Reasoning layer without coupling the architecture to one model. |

| Testing | pytest | Unit/integration testing. |

| Quality | Ruff + type checking | Consistent style and static quality checks. |

| Isolation | Docker | Controlled execution environments for verification. |


## Table 28

| TECHNOLOGY RULE Tools are replaceable implementation choices. The stable contracts are the internal models and module interfaces. |

| --- |


## Table 29

| Event | Required fields |

| --- | --- |

| discovery_completed | project_id, count, duration, findings |

| source_resolved | api_id, source_type, authority, resolver_version |

| collection_completed | source_id, fetched_at, status, bytes, duration |

| snapshot_created | snapshot_id, hash, source_id |

| change_detected | change_id, old_snapshot, new_snapshot, classification |

| impact_analyzed | change_id, affected_files, confidence/evidence |

| repair_attempted | repair_id, route, files_changed |

| verification_completed | repair_id, checks, result |


## Table 30

| proteus scan ./demo-app proteus sources list proteus monitor --once proteus changes proteus impact <change-id> proteus verify <repair-id> |

| --- |


## Table 31

| Stage | Build target | Definition of done |

| --- | --- | --- |

| A. Foundations | Models, config, logging, CLI skeleton, SQLite schema | Project installs reproducibly and core models are tested. |

| B. Discovery | Manifest/import/URL/runtime candidate detection | A sample repository produces a trustworthy API inventory. |

| C. Intent | LLM provider interface + structured intent profile | A discovered usage produces validated monitoring intent. |

| D. Resolution | Provider registry + source verification | Each intent maps to verified sources or a clear unresolved state. |

| E. Monitoring | Collector, scheduler, caching, snapshot store | Current state can be fetched repeatedly and historical snapshots are retained. |

| F. Change Engine | Normalizer + semantic diff + events | Controlled API changes produce structured, traceable events. |

| G. Impact | SDK/HTTP mapping + source locations | Relevant changes map to actual consumer usage. |

| H. Repair | Deterministic rules + LLM-assisted plans | A selected repair route produces a reviewable patch or manual action. |

| I. Verification | Baseline, tests, replay, evidence report | Repairs receive a verified/draft/unresolved outcome. |

| J. Evaluation | Controlled benchmark and failure analysis | System performance and limitations are measured honestly. |


## Table 32

| Repository   -> discover one SDK/API   -> profile intent   -> resolve 2-3 authoritative sources   -> collect + snapshot   -> modify a controlled fixture   -> detect change   -> produce evidence-backed report |

| --- |


## Table 33

| Metric | Definition |

| --- | --- |

| API discovery precision | Fraction of reported API dependencies that are real dependencies. |

| API discovery recall | Fraction of known external APIs in the test repository that were found. |

| Change detection accuracy | Agreement between known controlled changes and emitted structured changes. |

| Consumer relevance precision | Fraction of reported impacts that truly affect the consumer code. |

| False-positive rate | Unchanged or irrelevant usage that is incorrectly flagged. |

| Latency | Time from scheduled source collection to persisted change event. |

| LLM cost | Number of LLM calls/tokens used per repository and per discovered API. |

| Verification success | Fraction of repair attempts that pass the selected verification gates. |


## Table 34

| RESEARCH DISCIPLINE Do not report invented accuracy or performance figures. Measurements belong in the evaluation stage after reproducible experiments are completed. |

| --- |


## Table 35

| Risk | Impact | Mitigation |

| --- | --- | --- |

| Provider has no OpenAPI or reliable changelog | Medium/High | Use layered source resolution plus runtime observation. |

| Dynamic code hides API usage | High | Combine static and runtime evidence; report ambiguity explicitly. |

| LLM hallucinates a resource or migration | High | Verify provider sources deterministically; LLM is not truth source. |

| Provider rate limits or blocks monitoring | Medium | Backoff, caching, source-specific schedules and authorized access. |

| False positives from generic SDK names | Medium | Require AST/context confirmation and evidence merging. |

| Repair passes compilation but changes behavior | High | Use replay and behavior assertions in later verification stage. |

| Scope expands too quickly | High | Follow staged development path and maintain a strict non-goals list. |


## Table 36

| BASELINE ARCHITECTURE Repository discovery -> intent profiling -> source resolution -> live collection -> snapshots -> normalization/diff -> consumer impact -> repair -> verification. |

| --- |