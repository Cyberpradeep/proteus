# HIGH-LEVEL DESIGN DOCUMENT


## PROTEUS

Repository-Aware API Evolution Monitoring,
Impact Analysis and Automated Repair

MUTHAYAMMAL ENGINEERING COLLEGE

Department of CSE (Cyber Security)
B.E. Cyber Security • Final Year • Batch 2023–2027

Document Version 1.0  •  Architecture Baseline


# 1. PURPOSE AND SCOPE

This High-Level Design (HLD) translates the PROTEUS project concept into a system-level architecture that the development team can implement and evolve without repeatedly redesigning the whole system. It intentionally stays above class-level and function-level details: those belong in the Low-Level Design (LLD).

The design is grounded in the project study and technical design already prepared by the team, and refined using current API, observability, secure-development and tooling documentation. The project study defines the core pipeline as API discovery, intent profiling, source resolution, live monitoring, snapshots, change detection, consumer impact analysis, repair planning and verification. [Project Study]


# 2. SYSTEM VISION

PROTEUS is a repository-aware software-maintenance system for applications that depend on external APIs. Its core purpose is to keep a useful, evidence-backed relationship between two evolving worlds: the consumer repository and the external API/provider ecosystem.

The intended result is not merely “API changed.” PROTEUS should eventually be able to say: a provider-side change occurred, this repository depends on the affected capability, these source locations are relevant, and the available evidence supports a specific action or a human-review outcome.


# 3. DESIGN DRIVERS

- Consumer relevance: monitor the API surface that matters to the specific repository instead of blindly monitoring the entire provider.

- Authoritative evidence: current API facts must come from verified provider resources, specifications, changelogs, SDK metadata or authorized runtime observations—not model memory.

- Deterministic core: use parsers, hashes, semantic diffs, rules and tests wherever a deterministic technique is practical.

- Provider agnosticism: provider-specific source locations and mappings live in adapters/registry data while the internal model remains common.

- Graceful uncertainty: the system must represent “unknown” and “cannot safely determine” as valid outcomes.

- Incremental delivery: the core foundation must be useful before automated repair is added.

- Secure by construction: repositories and fetched content are untrusted inputs; secrets and authorization decisions stay outside the LLM.


# 4. HIGH-LEVEL ARCHITECTURE

Fig. 1. High-level logical architecture of PROTEUS.

The architecture deliberately separates reasoning from evidence handling. The repository is analyzed to build an API inventory. An LLM may interpret the context and produce a structured intent profile. The resource resolver then maps that intent to verified provider resources. The collector fetches current data, the snapshot store preserves evidence, and the normalization/diff layers convert provider-specific changes into a common model. Later stages map changes back to consumer code and verify any proposed adaptation.


# 5. COMPONENTS AND RESPONSIBILITIES


# 6. END-TO-END DATA FLOW

Fig. 2. High-level data flow from repository discovery to evidence-backed reporting.

A central HLD rule is that each stage produces a typed artifact consumed by the next stage. This prevents provider-specific logic from leaking into the entire system and makes the system testable one boundary at a time.


# 7. API DISCOVERY AND CONSUMER MODEL

API discovery is the first operational capability because downstream monitoring is only useful when the system knows which external APIs the repository actually depends on. The discovery stage should combine cheap candidate extraction with deeper confirmation.

1.  Manifest scan: inspect package managers and dependency files for SDK/package candidates.

2.  Source scan: identify SDK imports, client construction, direct HTTP calls and URL/base-URL definitions.

3.  Configuration scan: inspect non-secret configuration for provider identifiers, hosts and endpoint templates.

4.  Runtime confirmation: where authorized and isolated, use runtime/network telemetry to confirm destinations and operations.

5.  Entity resolution: merge evidence from different sources that refers to the same provider/API dependency.

6.  Usage mapping: attach source file, line/range and operation-level evidence where possible.


# 8. INTENT PROFILING AND LLM TRUST BOUNDARY

The LLM has a narrow but useful job: interpret repository context and produce a structured description of what matters to the application. This follows the project study distinction that the LLM should identify intent and ambiguity while deterministic components discover sources, fetch facts, normalize, compare and validate. [Project Study]

The implementation should use a provider abstraction so the HLD is not coupled to one model vendor. The initial option may be Z.AI/GLM, but model name and endpoint should be configuration, not architectural constants. Repository text and fetched documents must be treated as untrusted content when supplied to the model; OWASP notes that indirect prompt injection can arrive through code, documentation, web pages and tool outputs and recommends separating untrusted data from trusted instructions, validating tool arguments and enforcing permissions outside the model. [11]


# 9. AUTHORITATIVE RESOURCE RESOLUTION

After intent profiling, PROTEUS must determine what current provider information is needed. The resolver should prefer machine-readable and authoritative sources and record why each source was accepted.


# 10. LIVE MONITORING AND COLLECTION

The collector is responsible for acquiring current state. It should prefer event-driven updates when a trustworthy provider event exists and use polling otherwise. Polling is therefore a collection mechanism, not the definition of the system.

HTTP cache validators such as ETag and Last-Modified should be retained when supplied so unchanged sources can be revalidated without repeatedly downloading the complete representation. Each job needs a timeout, bounded retries with backoff, idempotent execution and a clear source-health state.


# 11. OBSERVED VS. DECLARED API STATE

A provider specification describes intended or declared behavior; runtime evidence describes behavior that was actually observed in a specific environment. PROTEUS should preserve both instead of silently merging them.

This distinction is essential for the research contribution: it lets PROTEUS reason about actual consumer risk even when a pure specification diff is silent. The design still treats observed behavior as evidence scoped to the environment in which it was captured, not as a universal replacement for the provider contract.


# 12. NORMALIZATION AND CHANGE DETECTION

Provider documents vary in format and vocabulary. The normalizer creates a common internal state so later modules operate against one contract. For OpenAPI-backed APIs, PROTEUS should use mature semantic diff capabilities where possible rather than inventing a complete comparator.

oasdiff currently provides commands for full diff, consumer changelog and breaking-change detection, emits structured formats such as JSON/YAML, and explicitly distinguishes definite breaking changes (ERR), potential breaking changes (WARN) and non-breaking information (INFO). It also states that its verdict is based on the declared OpenAPI contract, not arbitrary runtime server behavior. [6]


# 13. CONSUMER IMPACT ANALYSIS

Change detection answers what changed at the provider. Impact analysis answers whether this repository actually depends on the changed capability. The HLD therefore models an API-to-code relationship rather than a simple provider-wide alert.

1.  Map provider operation to SDK symbol or direct HTTP pattern.

2.  Locate confirmed call sites using AST/tree analysis rather than text matches alone.

3.  Trace relevant arguments/properties into nearby data construction when necessary.

4.  Compare the changed element against the consumer usage.

5.  Combine static evidence with authorized runtime observations where available.

6.  Produce an impact class such as DIRECT, INDIRECT, TEST-ONLY, AMBIGUOUS or NOT-AFFECTED.


# 14. REPAIR PLANNING

Repair is deliberately downstream. The planner decides whether a change can be handled by a deterministic transformation, requires LLM assistance, or must remain a human-review case.

The research basis supports this conservative design. The selected MOBILESoft 2023 base paper automated web-service client adaptation but reported unsolvable breaking changes that required manual improvement to migration guidance; later FSE 2025 work also found LLM-assisted dependency repair feasible but far from universally reliable. [1], [4]


# 15. VERIFICATION AND EVIDENCE

Verification should start with a baseline run and proceed in layers. Compilation or type checking is useful but is not sufficient to demonstrate behavioral compatibility.


# 16. DATA ARCHITECTURE

The initial persistence model should be relational and intentionally small. SQLite is sufficient for a local prototype; the schema should be portable to PostgreSQL if the deployment model later becomes multi-user or server-based.


# 17. DEPLOYMENT ARCHITECTURE

Fig. 3. Initial local deployment model and expansion path.

The recommended starting deployment is a local CLI because it keeps repository access, credentials and runtime experiments under the developer’s control. A later service mode can reuse the same core package and contracts. The architecture therefore separates the engine from the presentation/service layer.


# 18. SECURITY ARCHITECTURE AND TRUST BOUNDARIES

PROTEUS can handle source code, configuration, third-party content and credentials. Security is therefore a first-class architectural concern, especially because the system may fetch URLs discovered from untrusted inputs and may send repository context to an LLM.

These controls align with NIST’s Secure Software Development Framework, which recommends integrating secure-development practices into the SDLC; NIST’s current publication set also includes a draft Rev. 1 / Version 1.2 update released in December 2025. [9]


# 19. RELIABILITY AND FAILURE HANDLING


# 20. OBSERVABILITY AND AUDIT TRAIL

Runtime evidence should use common telemetry concepts where possible. OpenTelemetry defines HTTP semantic conventions for client/server spans and standardizes attributes such as HTTP method and URL-related information; its general semantic conventions are intended to make telemetry consistent across languages and systems. [8]


# 21. SOFTWARE ENGINEERING BASELINE


# 22. NON-FUNCTIONAL REQUIREMENTS


# 23. DEVELOPMENT PATH

The HLD supports incremental implementation. Each stage should be independently testable before the next stage is added.


# 24. EVALUATION FRAMEWORK

The project should be evaluated as an engineering system, not only as an LLM demo. The base literature establishes that API evolution and breaking-change identification are measurable problems; the 2024 semantic-versioning study analyzed 3,075 APIs and found that many providers do not consistently signal breaking changes through major version increments. [3]


# 25. ARCHITECTURAL TRADE-OFFS


# 26. RESEARCH AND INDUSTRY GROUNDING

The architecture combines established ideas rather than claiming that each individual component is new. The selected 2023 MOBILESoft paper demonstrates automated adaptation from API evolution patterns and migration guides; its evaluation covered 13 web-service version increments, 3,896 changes and 1,132 breaking changes, with 86.1% of changes correctly identified and 424 breaking changes treated as unsolvable automatically. [1]

The 2024 Journal of Systems and Software study found that practitioners still face manual change-impact analysis, ineffective communication of changes and consumer reliance on outdated versions, and explicitly identifies automated change-impact analysis as an open direction. [2] The 2024 semantic-versioning study likewise shows that breaking changes are not reliably communicated by version numbers alone. [3]

For implementation, OpenAPI provides a programming-language-agnostic interface description for HTTP APIs; the current published site lists OpenAPI 3.2.1 among the specification versions. [5] oasdiff supplies semantic diff/breaking-change machinery rather than requiring the project to reinvent a full OpenAPI compatibility engine. [6]

For secure engineering, NIST SSDF provides a baseline for integrating secure-development practices into the SDLC, while OWASP guidance is directly relevant to the repository/document/URL trust boundaries in a system that uses LLMs and fetches provider resources. [9]–[11]


# 27. EXPLICIT SYSTEM BOUNDARIES

- PROTEUS does not claim to know every private/internal API in a repository unless the necessary evidence is available and authorized.

- Provider-declared contract and observed runtime behavior are stored as different evidence classes; observed behavior does not silently replace the contract.

- The system does not bypass CAPTCHA, MFA, bot protection or other provider security controls.

- Automatic repair is never the default for ambiguous or high-risk changes.

- Runtime execution of scanned repositories is performed only in authorized, isolated environments.

- The initial implementation targets common web APIs and repository patterns; unsupported languages/providers produce explicit “not supported” or “unresolved” states.


# 28. APPROVAL CHECKLIST FOR DEVELOPMENT

- Architecture diagram and component responsibilities approved by the team.

- Internal artifact contracts agreed before module implementation.

- Provider adapter/source registry format defined.

- Secret-handling and SSRF controls included before remote fetching is enabled.

- Baseline repository fixture and controlled API-change fixture selected.

- Unit/integration/e2e test layout created before expanding provider coverage.

- Git branching and review workflow agreed by all four members.


# 29. REFERENCES

[1] P. Schmiedmayer, A. Bauer, and B. Bruegge, “Reducing the Impact of Breaking Changes to Web Service Clients During Web API Evolution,” 2023 IEEE/ACM 10th International Conference on Mobile Software Engineering and Systems (MOBILESoft), 2023, DOI: 10.1109/MOBILSoft59058.2023.00008.

[2] A. Lercher et al., “Microservice API Evolution in Practice: A Study on Strategies and Challenges,” Journal of Systems and Software, vol. 215, 2024, Art. no. 112110, DOI: 10.1016/j.jss.2024.112110.

[3] S. Serbout and C. Pautasso, “How Many Web APIs Evolve Following Semantic Versioning?,” ICWE 2024, pp. 344–359, DOI: 10.1007/978-3-031-62362-2_25.

[4] L. Fruntke and J. Krinke, “Automatically Fixing Dependency Breaking Changes,” Proceedings of the ACM on Software Engineering, FSE, vol. 2, 2025, pp. 2146–2168, DOI: 10.1145/3729366.

[5] OpenAPI Initiative, “OpenAPI Specification v3.2.1,” Sep. 2026.

[6] oasdiff, “OpenAPI Diff and Breaking Changes,” GitHub project documentation, accessed 2026.

[7] Tree-sitter, “Tree-sitter Documentation,” parser generator and incremental parsing library, accessed 2026.

[8] OpenTelemetry, “Semantic Conventions for HTTP Spans and General Telemetry,” accessed 2026.

[9] NIST, “Secure Software Development Framework (SSDF) Version 1.1,” SP 800-218, 2022; Rev. 1 / Version 1.2 initial public draft, Dec. 2025.

[10] OWASP, “Server-Side Request Forgery Prevention Cheat Sheet,” accessed 2026.

[11] OWASP, “LLM Prompt Injection Prevention Cheat Sheet,” accessed 2026.

[12] Pydantic, “Models and Validation,” official documentation, accessed 2026.


# Tables


## Table 1

| DESIGN PURPOSE Define the system-level architecture, component boundaries, trust model, data flow, technology choices and engineering constraints that will guide implementation. |

| --- |


## Table 2

| Poovarasan S | 23CY038 |

| --- | --- |

| Sachin P | 23CY045 |

| Malleshwaran P | 23CY030 |

| Pradeep S | 23CY039 |


## Table 3

| HLD BOUNDARY The HLD defines components, responsibilities, major interfaces, trust boundaries, data flow, deployment shape, engineering constraints and acceptance criteria. It does not prescribe every class, function, database index or UI screen. |

| --- |


## Table 4

| World | What evolves | What PROTEUS needs to know |

| --- | --- | --- |

| Consumer / repository | Source code, SDK usage, configuration, tests, runtime calls | Which APIs are used, where they are used, why they matter, and what assumptions the application makes |

| Provider / API | Endpoints, parameters, schemas, versions, models, lifecycle, documentation, runtime behavior | What the current API state is, what changed, when it changed, and which evidence supports the change |


## Table 5

| Component | Responsibility | Primary input | Primary output |

| --- | --- | --- | --- |

| API Discovery | Identify candidate and confirmed external API dependencies from manifests, imports, HTTP calls, configuration and authorized runtime evidence. | Repository | API Inventory |

| Intent Profiler | Interpret application context and identify the API capabilities/properties that matter. | API usage + bounded code context | Monitoring Intent |

| Resource Resolver | Map monitoring needs to authoritative provider resources and verify candidates. | Provider identity + Monitoring Intent | Source Registry |

| Collector | Fetch current source state using polling or events, caching validators, timeouts and bounded retries. | Source Definition | Raw Snapshot |

| Snapshot Store | Persist timestamped evidence and metadata needed for reproducible comparisons. | Raw Snapshot | Snapshot history |

| Normalizer | Convert provider-specific resources into a provider-neutral contract/state representation. | Raw Snapshot | Normalized State |

| Change Engine | Compare states and classify endpoint, parameter, schema, lifecycle and other supported changes. | Previous + current normalized state | Change Events |

| Impact Analyzer | Map a change to actual SDK/direct-HTTP usage and relevant source locations/assumptions. | Change Event + consumer model | Impact Result |

| Repair Planner | Choose deterministic, LLM-assisted or human-review route for an affected usage. | Impact Result + migration evidence | Repair Plan |

| Verifier | Run controlled checks and aggregate evidence; reject or downgrade unsupported repairs. | Repair + test environment | Verification Report |

| Orchestrator / CLI | Coordinate runs, persist state, surface results and manage user-triggered actions. | User command / scheduled job | Reports and job state |


## Table 6

| Artifact | Meaning | Must contain |

| --- | --- | --- |

| API Inventory | What the repository appears to depend on | Provider identity, base URL/host evidence, SDK/package evidence, operation candidates, source locations, confidence |

| Monitoring Intent | Why a discovered API matters | Application purpose, relevant capability, model/resource dependency, relevant request/response/lifecycle properties |

| Source Registry | Where current evidence is obtained | Source type, URL/endpoint, authority, collection method, schedule policy, validation status |

| Raw Snapshot | Exact fetched evidence | Timestamp, status, content hash, cache headers, raw representation or immutable reference |

| Normalized State | Provider-neutral representation | Endpoints/operations, schemas/parameters, lifecycle fields, model/resource state as applicable |

| Change Event | What changed | Target, change type, old/new state, severity, evidence references, detection timestamp |

| Impact Result | Whether consumer code is affected | Call sites, mapping method, changed element, assumption evidence, impact class |

| Verification Report | Whether an adaptation can be trusted | Baseline, checks run, results, failures, evidence and final decision |


## Table 7

| DISCOVERY PRINCIPLE Package presence is evidence of a candidate dependency, not proof that the application actively uses that API. Stronger confidence comes from combining dependency, source-code and runtime evidence. |

| --- |


## Table 8

| LLM may do | LLM must not do |

| --- | --- |

| Infer application purpose from bounded code context. | Invent the current API state. |

| Identify capabilities or API properties likely relevant to that purpose. | Be treated as the authoritative source for deprecation, endpoint existence or parameter truth. |

| Interpret ambiguous migration prose and propose a mapping hypothesis. | Make authorization or secret-handling decisions. |

| Return structured output matching a schema. | Apply source-code changes directly without deterministic validation and testing. |


## Table 9

| Source class | Typical use | Authority / treatment |

| --- | --- | --- |

| Live provider resource | Current models, supported capabilities, live resource catalog | Highest for current runtime state when an official endpoint exists |

| OpenAPI / API specification | Endpoints, methods, parameters, schemas and declared lifecycle | Highest for declared HTTP contract; OpenAPI 3.2.1 is currently a published specification version. [5] |

| Official changelog / release notes | Provider-side changes and announcements | High; preserve retrieved source and timestamp |

| Official deprecation / migration docs | Lifecycle deadlines and recommended migrations | High; useful when contract diff alone lacks migration semantics |

| SDK registry / release | Consumer-facing package version and API surface | High for SDK evidence; cross-check against provider docs |

| Runtime observation | What the application actually sent/received | Strong observational evidence, but scoped to observed traffic and environment |


## Table 10

| SOURCE RESOLUTION RULE LLM-discovered URLs are candidates. PROTEUS should verify domain/authority, content type, expected structure and redirect chain before promoting a source into the trusted Source Registry. |

| --- |


## Table 11

| Source | Preferred method | Prototype policy |

| --- | --- | --- |

| Official live resource API | Direct request; event/webhook when available | Higher frequency, provider-specific |

| OpenAPI specification | HTTP fetch + conditional request | Moderate frequency |

| Changelog / deprecation | HTTP fetch / structured parser | Daily or twice daily |

| SDK package registry | Registry metadata | Daily |

| Runtime telemetry | Event-driven observation | As authorized traffic occurs |


## Table 12

| Declared state | Observed state | Interpretation |

| --- | --- | --- |

| OpenAPI says field is required | Observed test traffic omits the field and still succeeds | Contract/behavior mismatch candidate; do not overwrite declared truth |

| Response schema defines fields A, B | Observed response contains additional field C | Undocumented-behavior candidate |

| Schema unchanged | Observed ordering/status/semantics changed | Behavioral drift candidate requiring targeted verification |

| Model listed as available | Provider lifecycle source says deprecated/shutdown | Lifecycle conflict to resolve using authoritative sources and timestamps |


## Table 13

| Change family | Examples | HLD treatment |

| --- | --- | --- |

| Endpoint | Added, removed, path/method changed | Create structured change event |

| Request | Required parameter added, type changed, enum narrowed | Classify compatibility risk |

| Response | Field removed, type changed, response removed | Flag consumers that read the affected element |

| Lifecycle | Deprecated, sunset/shutdown announced | Create lifecycle event with deadline/replacement evidence |

| Documentation | Description/example-only changes | Keep as low-impact information unless linked to migration guidance |

| Behavioral candidate | Runtime result differs without a declared schema change | Preserve as observed-vs-declared evidence for later impact/verification |


## Table 14

| TARGET OUTCOME A developer should receive “Stripe /payment_intents changed and src/payment_service.py:42 is likely affected,” not merely “Stripe changed.” |

| --- |


## Table 15

| Route | Use when | Required control |

| --- | --- | --- |

| Deterministic | Known rename, URL update, enum replacement, required-field insertion with a verified value source | AST validation + build/type/test checks |

| LLM-assisted | Migration prose or complex source context is ambiguous | Bounded context + structured plan + deterministic validation |

| Human review | Business semantics unclear, conflicting evidence, missing required value, unsupported change | No automatic modification; produce evidence-backed report |


## Table 16

| Layer | Question |

| --- | --- |

| Baseline | Was the repository already failing before the repair? |

| Static validation | Does the edited source remain syntactically and type-wise valid? |

| Project tests | Do existing unit/integration tests still pass relative to baseline? |

| Targeted migration test | Does the changed API interaction behave as expected? |

| Replay / behavioral check | Does a representative interaction still produce the intended outcome? |


## Table 17

| VERIFICATION DECISION VERIFIED REPAIR only when the configured evidence gates pass. Otherwise return DRAFT FOR REVIEW or CANNOT SAFELY DETERMINE. Never convert an uncertain result into a false “success.” |

| --- |


## Table 18

| Entity | Core fields | Purpose |

| --- | --- | --- |

| Project | id, name, repository path, created_at | Root object for analysis |

| API Dependency | id, project_id, provider, base_url, sdk, confidence | What the repository depends on |

| API Usage | id, api_id, method, path/symbol, file, line, source_type | Where/how the API is used |

| Source | id, api_id, type, location, authority, collection_policy | Where current evidence comes from |

| Snapshot | id, source_id, fetched_at, hash, status, raw_ref | Historical evidence |

| Normalized State | id, snapshot_id, schema/version, payload | Provider-neutral state |

| Change Event | id, old_state, new_state, type, severity, evidence | Detected evolution |

| Impact Result | id, change_id, consumer location, classification, confidence | Consumer relevance |

| Repair / Verification | id, impact_id, plan, checks, status, evidence | Later adaptation lifecycle |


## Table 19

| Risk / boundary | Control |

| --- | --- |

| Secrets in repository | Exclude tokens, cookies, private keys and .env secrets from LLM context and logs; support explicit secret scanning before model calls. |

| SSRF during source resolution | Allow only expected schemes; verify provider domains; validate redirects; block private/internal address targets. OWASP specifically identifies unrestricted URL fetching as an SSRF risk. [10] |

| Prompt injection in repository/docs | Treat repository and fetched text as untrusted data; separate instructions from data; never let content redefine tools/policies. [11] |

| Untrusted repository execution | Prefer static analysis; runtime observation only in an authorized isolated environment. |

| Provider credentials | Least privilege, short-lived/scoped credentials where possible, timeouts and rate limits. |

| AI output misuse | Validate structured output against a schema; never use model text directly as an executable command or patch without checks. |

| Destructive actions | Keep automatic repair non-destructive; require review before merging or applying risky changes. |


## Table 20

| Failure | Expected HLD behavior |

| --- | --- |

| Provider timeout / 5xx | Bounded retries with backoff; mark source unhealthy; continue unrelated jobs. |

| HTTP 429 | Honor retry/backoff policy and rate budget; do not create duplicate state. |

| Invalid source payload | Reject normalization; preserve raw evidence and report parse failure. |

| LLM timeout / malformed output | Retry within budget; validate output; fall back to deterministic analysis or unresolved state. |

| Partial provider availability | Process healthy sources and explicitly label missing sources. |

| Storage failure | Fail the affected job without claiming new state was stored; maintain idempotent job keys. |

| Verification failure | Do not publish a verified repair; return draft/review/failure status. |


## Table 21

| Signal | Examples |

| --- | --- |

| Structured logs | job started/completed, source failure, parser failure, change emitted, verification result |

| Metrics | sources checked, fetch success rate, unchanged ratio, changes detected, LLM calls, token/cost budget if available |

| Traces | repository scan, source fetch, normalization, diff and verification spans |

| Audit evidence | source URL, authority, timestamp, hash, code location, change classification and decision |


## Table 22

| Area | Baseline |

| --- | --- |

| Language / environment | Python with uv-managed reproducible environment |

| Source control | Git + GitHub; feature branches and reviewed pull requests |

| Parsing | Python AST initially; Tree-sitter abstraction for multi-language growth. Tree-sitter is designed as an incremental, robust parser generator/library with official Python bindings. [7] |

| HTTP | HTTPX for sync/async collection, reusable clients, timeouts and connection control |

| Models | Pydantic for typed validated internal artifacts; its models validate untrusted data into typed structures. [12] |

| Storage | SQLite first; portable schema for PostgreSQL later |

| Scheduling | APScheduler or equivalent for recurring jobs; provider events preferred when available |

| Contract diff | OpenAPI + oasdiff/equivalent for declared contract comparisons |

| Runtime evidence | OpenTelemetry-compatible traces/telemetry where authorized |

| LLM | Provider abstraction; initial Z.AI/GLM option; structured output only |

| Testing | pytest; unit, integration, end-to-end and evaluation tests |

| Quality | Ruff + type checking + CI gates |

| Isolation | Docker for controlled execution/verification environments |


## Table 23

| TECHNOLOGY PRINCIPLE Libraries are replaceable. The stable architectural assets are the typed internal models, module boundaries, evidence model and provider-neutral state representation. |

| --- |


## Table 24

| ID | Requirement | Acceptance direction |

| --- | --- | --- |

| NFR-01 | Determinism | Same inputs and pinned tool versions produce the same normalized/diff result. |

| NFR-02 | Traceability | Every change report points to source and timestamped snapshot evidence. |

| NFR-03 | Isolation | Failure of one provider or one LLM call does not terminate unrelated monitoring jobs. |

| NFR-04 | Security | Secrets are excluded from model context/logs; source fetching applies SSRF controls. |

| NFR-05 | Extensibility | Adding a new provider should primarily require source definitions/adapter logic, not changes across the core pipeline. |

| NFR-06 | Performance | Cheap candidate filters should precede expensive AST/LLM analysis. |

| NFR-07 | Reproducibility | Snapshots and configuration allow a past comparison to be replayed. |

| NFR-08 | Human control | Uncertain or risky changes must produce a reviewable result instead of automatic mutation. |


## Table 25

| Stage | System capability | Exit condition |

| --- | --- | --- |

| Foundation | Repository scan + API inventory | Multiple API dependency types are discovered with evidence. |

| Intent | Structured consumer-intent profiles | LLM output validates against schema and does not supply live facts. |

| Sources | Provider source registry + verification | Discovered sources are classified and verified. |

| Collection | Fetch + schedule + snapshots | Repeatable snapshots with cache validators and failure states. |

| Change | Normalization + semantic diff | Controlled changes become structured events. |

| Impact | API-to-code mapping | Relevant call sites can be found for supported usage patterns. |

| Repair | Deterministic / LLM-assisted planning | Plans are validated before code modification. |

| Verification | Build/tests/replay evidence | Repair outcomes are VERIFIED, DRAFT or CANNOT SAFELY DETERMINE. |

| Evaluation | Benchmark and controlled scenarios | Metrics quantify discovery, change detection, false positives, impact accuracy and repair verification. |


## Table 26

| Metric | What it measures |

| --- | --- |

| API discovery precision / recall | How well PROTEUS identifies real API dependencies and avoids package-only false positives. |

| Source-resolution success | Fraction of discovered monitoring intents mapped to verified authoritative resources. |

| Snapshot freshness / completeness | Whether scheduled collection maintains usable current state and clear failure status. |

| Change detection precision / recall | Ability to surface controlled contract changes without excessive noise. |

| Consumer-impact accuracy | Whether reported call sites actually depend on the changed capability. |

| Repair acceptance rate | Fraction of proposed repairs that pass verification gates. |

| False auto-repair rate | Unsafe changes that should have been blocked; target should be effectively zero for verified status. |

| Cost / latency | Collection time, LLM call count and optional model/token expenditure for reasoning steps. |


## Table 27

| Decision | Why | Trade-off |

| --- | --- | --- |

| CLI-first | Keeps development and secrets local; fastest route to a demonstrable core. | Less convenient for multi-user teams until service layer is added. |

| LLM as interpreter, not authority | Reduces hallucinated “live truth” and keeps facts reproducible. | Requires more deterministic engineering around source resolution and normalization. |

| SQLite first | Simple zero-service persistence. | Limited concurrency/remote operation at larger scale. |

| Provider-neutral model | Makes multiple APIs share one pipeline. | Normalization has to handle provider-specific edge cases. |

| Deterministic repair first | Predictable and testable. | Some semantically complex migrations remain manual or LLM-assisted. |

| Evidence retention | Supports auditability and research reproducibility. | Consumes storage and requires retention policies. |


## Table 28

| DESIGN BASELINE The HLD is approved as the architecture baseline for implementation. Detailed classes, function signatures, SQL DDL, provider adapter code and UI/API endpoints belong in the LLD and implementation repositories. |

| --- |