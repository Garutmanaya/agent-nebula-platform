# REST and FastAPI Integration

Agent Runtime can attach opt-in routes to a caller-owned FastAPI application or create a managed application through the standalone preset.

Possible routes include:

```text
GET  /.well-known/agent-card.json
GET  /.well-known/oauth-protected-resource
GET  /health
GET  /ready
GET  /api/v1/metrics
POST /api/v1/skills/{skill_id}
POST /api/v1/a2ui/actions
POST /a2a
POST /a2a/tasks
GET  /a2a/tasks/{task_id}
POST /a2a/tasks/{task_id}/cancel
GET  /a2a/tasks/{task_id}/events
```

Routes are thin adapters. They map HTTP inputs to runtime services and map typed runtime errors to safe responses. They do not implement OAuth, DPoP, scope policy, or business logic.
