# Agent Card and Protected Resource Metadata

Agent Runtime supports two modes:

1. inject complete authoritative documents;
2. construct documents with typed builders.

Builders preserve unknown top-level and extension fields. They do not infer missing ownership, endpoints, protocols, skills, or scopes from names or unrelated configuration.

Cross-document validation checks:

```text
runtime skills ↔ Agent Card skills
Agent Card required_scopes ⊆ Protected Resource Metadata scopes_supported
```

Protected Resource Metadata validation is delegated to `agent-nebula-sdk` where available. Full normative validation of every Agent Card protocol version remains an SDK concern.
