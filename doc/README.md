# PROTEUS — Antigravity Development Pack

## What each file is for

| File | Purpose |
|---|---|
| `AGENTS.md` | Standing coding-agent rules: safety, Git isolation, verification, architectural guardrails. |
| `docs/PROTEUS_DEVELOPMENT_CONTRACT.md` | PROTEUS-specific implementation contract and milestone boundaries. |
| `docs/HLD.md` | System-level architecture, component boundaries, data flow, deployment and trust boundaries. |
| `docs/TDD.md` | Technical design, requirements, interfaces, storage, security, testing and technology baseline. |
| `assets/` | Architecture/data-flow/deployment visuals used by the design documents. |

## Required reading order for Antigravity

```text
AGENTS.md
   ↓
docs/PROTEUS_DEVELOPMENT_CONTRACT.md
   ↓
docs/HLD.md
   ↓
docs/TDD.md
```

## Implementation rule

Do not build the entire architecture in one pass.

Start with:

```text
API Discovery
→ Intent Profiling
→ Resource Resolution
→ Live Collection
→ Snapshot Storage
→ Normalization
→ Change Detection
→ Change Report
```

Only after this foundation is working and tested should the team move to consumer-impact analysis, repair planning, and verification.

## Source of truth hierarchy

```text
Project HLD/TDD
    ↓
implementation contracts
    ↓
provider authoritative sources
    ↓
runtime evidence
    ↓
LLM interpretation when necessary
```

For current provider facts, provider evidence outranks model memory.
