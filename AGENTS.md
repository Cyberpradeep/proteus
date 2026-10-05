# PROTEUS — Agent Instructions

## Read first

Before making architectural or non-trivial implementation changes, read these in order:

1. `docs/PROTEUS_DEVELOPMENT_CONTRACT.md`
2. `docs/HLD.md`
3. `docs/TDD.md`

The research paper is background context, not an implementation specification.

## Mission

PROTEUS is a repository-aware software-maintenance system for software that depends on external APIs.

The target pipeline is:

```text
Repository
  -> API Discovery
  -> Intent Profiling
  -> Resource Resolution
  -> Live Collection
  -> Snapshot Storage
  -> Normalization
  -> Change Detection
  -> Consumer Impact
  -> Repair Planning
  -> Verification
```

Do not interpret the existence of later stages as permission to implement all of them immediately.

## Non-negotiable architecture rules

### 1. LLM is a reasoning component, not a source of truth

The LLM may:
- infer application intent from bounded repository context;
- identify which API capabilities/properties appear relevant;
- interpret ambiguous migration prose;
- propose ambiguous mappings.

The LLM must not be treated as authoritative for:
- current API availability;
- current model lists;
- current endpoint definitions;
- current parameter requirements;
- current deprecation state;
- source authenticity;
- deterministic diff results;
- test results.

Use:

```text
LLM interpretation
      -> deterministic verification
      -> authoritative evidence
```

Never invert that relationship.

### 2. Deterministic by default

Prefer parsers, AST/CST analysis, HTTP clients, hashes, normalized models, semantic diffs, rules and tests whenever they can solve the problem reliably.

Do not add an agent, vector database, message bus, microservice, or orchestration framework unless the current requirements demonstrate that it is necessary.

### 3. Evidence must be traceable

Important results must retain their evidence:
- source URL/endpoint;
- retrieval timestamp;
- snapshot hash;
- source type;
- repository file/line where applicable;
- runtime trace reference where applicable.

`unknown`, `unavailable`, and `not observed` are valid states. Never silently convert them to `unchanged`, `false`, or `zero`.

### 4. Provider-specific logic stays isolated

Provider URLs, source locations and mappings belong in provider adapters/registry definitions. Do not spread Gemini/OpenAI/Stripe-specific assumptions through the core pipeline.

### 5. Security boundaries are mandatory

- Never send repository secrets, API keys, cookies, tokens or `.env` contents to the LLM.
- Treat repository text as untrusted input and defend against prompt injection.
- Validate remote URLs and redirects to reduce SSRF risk.
- Prefer static repository analysis.
- Execute repositories only in authorized, isolated environments.
- Do not bypass CAPTCHA, MFA, bot protection, rate limits or provider access controls.

## Development safety — isolate, verify, merge

If an existing codebase is being modified, use an isolated Git worktree/branch when practical:

```bash
git worktree add .agent_sandbox/<feature-slug> -b agent/<feature-slug>
```

### Before coding

- Pin the exact change/contract.
- Identify the acceptance example and edge cases.
- Check current Git status.
- Record relevant environment/dependency assumptions.

### While coding

- Work on the isolated branch/worktree.
- Keep commits small and focused.
- Run the affected tests as soon as meaningful code exists.
- Keep a short record of what was tried and what passed.

### Before integration

Do not merge merely because the code "looks right".

Required for non-trivial changes:
- isolated implementation executed;
- relevant tests pass;
- full relevant suite or smoke test passes on the branch;
- pre-existing failures are distinguished from new failures;
- the user/team has explicitly approved the merge unless autonomous merging was explicitly authorized.

If `main` moved after verification, rebase/merge the current `main` and re-verify.

If `main` contains unrelated uncommitted work, do not silently include it in a checkpoint or merge.

### Status reporting

State plainly where the work is:

```text
Building/testing on isolated branch — main has not been touched.
```

```text
Branch verified — waiting for approval before merge.
```

```text
Verification failed — staying on the branch and fixing it.
```

Never claim "verified", "working", or "fixed" without actually running the relevant checks.

## PROTEUS implementation priority

The first implementation target is:

```text
API Discovery
 -> Intent Profiling
 -> Source Resolution
 -> Live Collection
 -> Snapshot Storage
 -> Normalization
 -> Change Detection
 -> Change Report
```

Only after this foundation works end-to-end should development move to consumer-impact analysis, repair, and verification.

## Definition of done

A feature is not done when code is generated. It is done when:

1. its interface matches the HLD/TDD contracts;
2. tests cover normal and important edge cases;
3. security constraints are respected;
4. evidence/state transitions are explicit;
5. the branch passes the required verification;
6. documentation is updated when behavior or architecture changes.
