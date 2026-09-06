# Dependency and Ownership Boundaries

## agent-nebula-sdk owns

- OAuth protocol behavior;
- JOSE, JWT, and JWK operations;
- RFC 7523 `private_key_jwt`;
- RFC 7638 thumbprints;
- RFC 8707 resource indicators;
- RFC 9068 access-token validation;
- RFC 9449 DPoP;
- protocol metadata validation where implemented;
- cryptographic key handling.

## Agent Runtime owns

- plugin composition and lifecycle;
- host-neutral ports and adapters;
- Agent Nebula REST integration;
- onboarding orchestration and recoverable cache;
- skill registry and invocation;
- REST/FastAPI and A2A adapters;
- A2UI application integration;
- document builders and cross-document consistency checks;
- health, metrics, telemetry, scheduler, and retry;
- embedded and standalone presets.

## Host application owns unless explicitly delegated

- business logic;
- authoritative domain data;
- process and deployment model;
- database and distributed state;
- external logging/telemetry platform;
- trusted A2UI renderer catalog;
- production certificate and secret provisioning;
- cloud-specific integration.

## Agent Nebula owns

- registration identity;
- Publisher and Provider ownership;
- lifecycle and trust state;
- OAuth client and protected-resource identifiers;
- enterprise policy and RBAC;
- discovery authority.

This separation prevents the runtime from becoming a second control plane or protocol stack.
