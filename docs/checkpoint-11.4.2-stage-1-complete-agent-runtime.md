# Checkpoint 11.4.2 — Stage 1: Complete Agent Runtime

## Objective

Make Agent Runtime role-neutral and capable of constructing common infrastructure plus enabled OAuth-client or provider security capabilities without requiring Agent Studio to assemble SDK objects.

## Implemented baseline

- Central `RuntimePathResolver` with application and product ownership roots.
- `product_root` support in Runtime application settings.
- One Runtime-owned INI loader for all `runtime.*` sections.
- Optional onboarding, OAuth-client, and protected-resource settings.
- Validation tied to enabled plugins.
- Role profile vocabulary for provider, OAuth client, orchestrator, and dual role.
- Conditional OAuth-client construction.
- Runtime-owned SDK-backed protected-resource construction.
- Runtime-managed provider JWKS transport cleanup.
- Runtime service container exposing only composed capabilities.
- Runtime attachment that injects owned services into plugins rather than requiring Studio construction.

## Stage boundary

Stage 1 completes Runtime APIs and ownership. Stage 2 must migrate STX Metro and Common Orchestrator to this single path and remove their remaining Runtime/protocol composition code. No new Studio business features belong in Stage 1.
