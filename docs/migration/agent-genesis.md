# Agent Genesis Migration

`agent-genesis-sdk` was the source of reusable integration behavior extracted into Agent Runtime. The target dependency graph is:

```text
agent-nebula-sdk
        ↑
agent-runtime
        ↑
Agent Studio and migrated agents
```

Recommended migration:

1. migrate one Provider Agent first;
2. compare onboarding, OAuth, DPoP, Agent Card, health, and A2A behavior;
3. run end-to-end regression tests against Agent Nebula;
4. move shared runtime logic out of the agent repository;
5. retain only domain configuration and business handlers;
6. retire `agent-genesis-sdk` after migration is proven rather than maintain two implementations indefinitely.
