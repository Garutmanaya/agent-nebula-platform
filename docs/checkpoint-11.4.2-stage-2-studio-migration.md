# Checkpoint 11.4.2 Stage 2 — Studio Migration

Stage 2 completes the Runtime composition consolidation begun in Stage 1.

Agent Runtime now exposes the reusable onboarding payload builders, protected OAuth/DPoP HTTP client, role-aware application builder, protected-resource service composition, configuration loader, path resolver, lifecycle, server, and cleanup used by Agent Studio applications.

Agent Studio applications now provide business components and metadata only. STX Metro and Common Orchestrator both use `RuntimeApplicationSettings.from_ini`, `RuntimeApplicationBuilder.build_services`, `RuntimeApplicationBuilder.attach`, and `RuntimeApplication.run`.

STX Metro no longer creates SSL contexts, HTTP clients, Nebula connectors, RuntimeContext, state stores, protected-resource SDK validators, lifecycle handlers, or Uvicorn servers. Its former `security.py` implementation has been removed. It parses only `[parking]` settings.

Common Orchestrator no longer maps `runtime.*` sections, constructs OAuth transport behavior, or owns server startup. It parses only `[browser]`, `[sessions]`, and `[ui]` and consumes Runtime's `ProtectedHttpClient` for secured provider invocation.

The shared generator emits one consolidated `application.conf` per application. Runtime sections are identical in structure and role-specific sections are selected through plugins and role profiles. STX Metro no longer receives a second infrastructure configuration file.

Repository boundary tests prohibit direct SDK imports and infrastructure construction in Studio.
