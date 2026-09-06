# Operational Verification

Run the complete test suite:

```bash
uv run pytest -q
```

Compile source and examples:

```bash
python3 -m compileall -q src tests examples
```

For a running agent, verify enabled endpoints:

```text
GET  /.well-known/agent-card.json
GET  /.well-known/oauth-protected-resource
GET  /health
GET  /ready
GET  /api/v1/metrics
POST /api/v1/skills/{skill_id}
POST /a2a
POST /a2a/tasks
POST /api/v1/a2ui/actions
```

Only endpoints backed by enabled components are attached. Protected operations require valid OAuth and DPoP inputs.

See [Security overview](../security/overview.md) and [Capability matrix](../reference/capability-matrix.md).
