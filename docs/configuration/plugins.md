# Plugin Enablement

Preset plugin settings use a three-state model:

| Value | Meaning |
|---|---|
| omitted / `None` | Compose automatically when required components exist |
| `true` | Require the capability; fail closed if dependencies are absent |
| `false` | Disable the capability even when compatible components exist |

Example:

```ini
[runtime.plugins]
onboarding = true
oauth_client = true
protected_resource = true
skills = true
agent_card = true
health = true
metrics = true
telemetry = true
scheduler = true
a2a = true
a2ui = false
```

Constructor composition remains authoritative. Flags do not create missing protocol services, business skills, documents, or telemetry destinations automatically.
