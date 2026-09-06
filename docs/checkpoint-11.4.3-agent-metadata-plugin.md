# Checkpoint 11.4.3 — Runtime Agent Metadata Plugin

Agent Runtime now owns verified retrieval, validation, caching, and selected-skill resolution for remote authoritative Agent Cards. Applications consume `AgentMetadataService`; they do not create HTTP clients, parse Agent Cards, infer OAuth scopes, or cache protocol metadata.

The service requires an absolute HTTPS Agent Card URL, rejects redirects and malformed documents, validates skill identity, preserves exact opaque `required_scopes`, and fails closed when the selected skill is absent or has no scopes for secured invocation. The Runtime application builder composes and registers the `agent.metadata` plugin for OAuth-client roles using the existing verified provider HTTP client.
