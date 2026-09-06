# Plugin Overview

Agent Runtime capabilities are optional plugins around a small lifecycle core.

| Plugin/capability | Main responsibility |
|---|---|
| Onboarding | Resolve/register with Agent Nebula and cache recoverable state |
| OAuth client | Request/cache audience- and scope-specific tokens and create DPoP headers |
| Protected resource | Validate RFC 9068 tokens, DPoP, audience, URI, method, replay, and scopes |
| Skills | Register typed business handlers and invoke through one security boundary |
| Agent server | Attach well-known, health, REST, A2A, A2UI, and metrics routes |
| A2A | Immediate calls plus asynchronous task lifecycle |
| A2UI | Validate declarative surfaces and route approved actions to skills |
| Metrics | Process-local counters, gauges, durations, and snapshot export |
| Telemetry | Structured non-secret runtime events to approved sinks |
| Scheduler | Startup, shutdown, one-shot, and interval jobs |

Each detailed document explains dependencies, behavior, security, and limitations.
