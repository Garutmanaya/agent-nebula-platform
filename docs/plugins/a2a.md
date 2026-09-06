# A2A Plugin

The A2A capability supports both immediate secure method dispatch and asynchronous tasks.

## Immediate invocation

`POST /a2a` maps an A2A method/skill request to the shared `SkillInvocationService`.

## Tasks

```text
POST /a2a/tasks
GET  /a2a/tasks/{task_id}
POST /a2a/tasks/{task_id}/cancel
GET  /a2a/tasks/{task_id}/events
```

Task states are `submitted`, `working`, `completed`, `failed`, and `canceled`. Events are ordered and can be replayed through SSE using sequence/`Last-Event-ID` semantics.

Protected task creation validates OAuth, DPoP, and scopes before persisting task ownership. Status, cancellation, and stream operations reauthenticate the caller.

The default store is in memory. Distributed persistence, leasing, retries, expiration, and worker coordination are not included yet.
