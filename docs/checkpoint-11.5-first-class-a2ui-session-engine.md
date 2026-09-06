# Checkpoint 11.5 — First-Class A2UI Session Engine

Checkpoint 11.5 promotes A2UI from surface validation into a first-class Agent Runtime capability. The implementation is domain-neutral and supports parking, travel, finance, CloudOps, healthcare, retail, and future Agent categories without domain branches in Runtime or Common Orchestrator.

## Ownership

`agent-nebula-sdk` remains authoritative for A2A/A2UI protocol documents and security behavior. Agent Runtime owns reusable session infrastructure, persistence, surface transitions, navigation, action history, synchronized data, provider task references, lifecycle, and service registration. Agent Studio consumes these services and owns only discovery decisions, business orchestration, catalogs, and the browser-facing application contract.

## Runtime package structure

```text
agent_runtime/a2ui/
├── actions/       action recording and dispatch coordination
├── data_model/    deterministic synchronized model updates
├── events/        typed non-secret session events
├── persistence/   memory and atomic JSON stores
├── session/       session lifecycle, participants, tasks, and snapshots
├── surfaces/      push, replace, append, back, and forward semantics
├── models.py      A2UI protocol-facing models
├── service.py     provider-side A2UI validation and action dispatch
└── validation.py  protocol and component policy
```

## Session state

A session owns the renderer capabilities, selected Agent, all participating Agents, a bounded surface stack, navigation cursor, synchronized data model, action audit records, A2A task/context references, status, and timestamps. Access tokens, DPoP proofs, private keys, and assertions are never persisted in the session.

## Surface operations

`PUSH` adds a surface and truncates abandoned forward history. `REPLACE` replaces the current surface. `APPEND` progressively adds messages/data to the current surface. `MODAL` is retained as an explicit semantic mode and currently uses stack behavior. Back and forward move only the cursor and never reinvoke a Provider.

## Persistence

The orchestrator profile enables `[runtime.a2ui_session]`. The default JSON store writes atomically beneath the instance runtime state directory. The memory store is intended for tests and explicitly ephemeral deployments.

## Multi-agent composition

Selecting or receiving a surface from an Agent adds that Agent to the session participant set. A single session can therefore retain surfaces and task references from multiple Agents. Checkpoint 11.5 provides the generic state model; domain-specific travel, finance, or CloudOps workflows remain Studio business composition.

## Progressive rendering and tasks

Provider response metadata may declare `surface_operation`, A2A `task_id`, `context_id`, and task status. Runtime preserves these values, updates the surface stack, and retains task references for reconnect and future streaming integration.

## Plugin and service

`A2UISessionPlugin` registers `a2ui.session`. `RuntimeApplicationBuilder` constructs `A2UISessionService` only when the plugin and settings are enabled. ORCHESTRATOR and DUAL_ROLE profiles enable the capability by default.

## Security

The session engine records only non-secret interaction state. Provider actions still pass through authoritative Agent Card scope resolution, OAuth resource indicators, private_key_jwt, DPoP, and the Runtime protected HTTP client. Session persistence does not replace or weaken those controls.
