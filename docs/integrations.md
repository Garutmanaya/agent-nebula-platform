# Integrations

## Purpose

`integrations/` contains optional product- or service-specific connectors. These integrations are not protocol definitions and must not become prerequisites for otherwise independent protocol operation.

The current integration is Agent Nebula.

## Agent Nebula layout

```text
integrations/nebula/
├── onboarding/
│   ├── models.py
│   ├── payloads.py
│   └── plugin.py
├── configuration.py
├── connector.py
└── registration.py
```

## Configuration

Nebula configuration is independent from A2A configuration. It defines Registry connectivity, TLS settings, and registration authentication required specifically for communicating with Agent Nebula.

This separation is intentional: an A2A provider or client must be able to operate without Agent Nebula Registry integration.

## Connector

`NebulaConnector` defines the integration boundary. `RestNebulaConnector` provides the REST implementation, while `DisabledNebulaConnector` represents explicitly disabled Registry integration without forcing callers to special-case missing infrastructure.

## Registration

`NebulaRegistrationClient` owns Registry registration communication. Registration is a Nebula integration concern; it is not part of the A2A protocol and must not be embedded into the generic A2A server/client implementation.

## Onboarding

The onboarding package contains typed settings, payload construction, and `OnboardingPlugin`.

Onboarding is a post-server lifecycle capability. The agent endpoint must already be reachable before onboarding starts because Registry processing can require callbacks to the agent. The plugin lifecycle therefore provides the `POST_SERVER` lifecycle boundary specifically for this type of integration.

## Independence from security protocols

Nebula registration authentication and agent endpoint OAuth security are separate concerns. Registering an agent with Agent Nebula does not define how an A2A caller authenticates to the agent, and an OAuth-protected A2A endpoint does not require Agent Nebula registration.

## Adding integrations

A new external product integration should live under `integrations/<name>/` when it is product-specific. Generic protocols belong under `a2a/` (for A2A); reusable security belongs under `security/`; generic lifecycle/configuration belongs under `platform/`.
