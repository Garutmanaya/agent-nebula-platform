# Claude and AI Coding Instructions

`AGENTS.md` is the authoritative engineering contract for this repository and the Agent Nebula ecosystem. Read it completely before modifying code. Also read:

- `docs/AGENT_ECOSYSTEM_DESIGN_AND_IMPLEMENTATION_REQUIREMENTS.md`
- `docs/RUNTIME_PLUGIN_AND_STUDIO_APPLICATION_IMPLEMENTATION_REQUIREMENTS.md`

Do not infer architecture from legacy code. Do not move protocol or infrastructure implementation into Agent Studio. Do not introduce application-specific Runtime configuration parsers or builders. Use the actual repository, current schemas, public Runtime APIs, and tests as the implementation baseline.

For every change, verify repository ownership, plugin completeness, configuration ownership, path ownership, lifecycle ownership, resource cleanup, security boundaries, and repository-boundary tests. If existing code conflicts with `AGENTS.md`, treat the code as migration debt and correct it at the owning layer rather than adding a local workaround.

Checkpoint 11.5: treat A2UI as a first-class Runtime capability. Do not place session persistence, navigation, synchronized data models, action history, task references, or multi-agent participant state in Agent Studio.
