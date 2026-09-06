# Onboarding Plugin

The onboarding plugin integrates an agent with Agent Nebula while preserving existing wire contracts.

## Flow

```text
build complete onboarding payload
        ↓
resolve existing registration by stable identity
        ↓
reuse authoritative registration when found
        ↓
otherwise register with configured authentication
        ↓
cache non-secret recovery state
```

## Responsibilities

- resolve-before-register idempotency;
- bounded retry orchestration;
- persistence of recoverable non-secret state;
- structured lifecycle events;
- no duplication of Agent Nebula onboarding protocol logic.

Local state is not authoritative. Agent Nebula remains the source of registration and OAuth identifiers.
