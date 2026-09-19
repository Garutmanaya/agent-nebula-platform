# A2A Schema Contract Extension

Agent Nebula Platform supports the A2A Schema Contract community extension Draft 0.1 for advertising machine-readable application payload contracts while preserving the official A2A 1.0 wire model.

The extension URI is `https://w3id.org/a2a-schema-contract/draft/0.1`. Platform publishes contracts only through `AgentCard.capabilities.extensions`; it does not add schema fields to `AgentSkill`. The draft's `skillIds` association is descriptive and is not used for runtime routing. Agent Nebula's independent skill-selection extension remains responsible for deterministic `AgentSkill.id` selection.

P1 supports inline JSON Schema Draft 2020-12 contracts for `application/json` input and output. A registered skill supplies an immutable, versioned `schema_contract_id` plus optional protocol-neutral input/output schemas. Platform converts those declarations to the draft extension catalog when composing the Agent Card.

The Schema Contract extension remains optional (`required=false`) because it is a data/discovery capability. P1 does not implement remote catalog/schema resolution, extension activation metadata, primary-Part metadata, or request/response boundary validation. Those behaviors require the remaining Draft 0.1 protocol machinery and must not be approximated with proprietary A2A fields.
