# AGENT_RUNTIME_HOME and Managed Paths

Standalone mode uses one external product root:

```bash
export AGENT_RUNTIME_HOME=/opt/airline-agent
```

The default configuration path is:

```text
$AGENT_RUNTIME_HOME/config/application.conf
```

`AGENT_RUNTIME_CONFIG` may select another configuration file.

Relative certificate, key, trust, state, telemetry, and secret paths are normalized beneath the runtime root. Traversal outside the root is rejected.

Embedded applications can provide explicit absolute, already-validated paths through their own adapters instead of using the managed root.
