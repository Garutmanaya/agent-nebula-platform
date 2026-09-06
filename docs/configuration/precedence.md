# Configuration Precedence

The effective configuration is merged in this order:

1. built-in non-secret defaults;
2. external INI configuration;
3. environment overrides;
4. explicit CLI overrides.

Later sources override earlier sources recursively.

Environment format:

```bash
AGENT_RUNTIME__SERVER__PORT=9443
AGENT_RUNTIME__PLUGINS__A2UI=false
```

CLI/programmatic overrides:

```python
settings = StandaloneRuntimeSettings.from_sources(
    command_line={
        "server.port": 9443,
        "logging.level": "DEBUG",
    }
)
```

Values are parsed into typed scalars, arrays, or objects before Pydantic validation. Invalid combinations fail at startup.
