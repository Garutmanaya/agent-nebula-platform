# Configuration Overview

Standalone mode uses deterministic layered configuration. Embedded applications may inject their own configuration provider and skip the built-in loader.

```text
built-in non-secret defaults
→ external INI file
→ AGENT_RUNTIME__SECTION__FIELD environment variables
→ explicit CLI override mapping or key=value sequence
```

Configuration is parsed and validated once at the composition boundary. Plugins do not independently read environment variables or files.

See:

- [Precedence](precedence.md)
- [Runtime home](runtime-home.md)
- [Secrets](secrets.md)
- [TLS](tls.md)
- [Plugin enablement](plugins.md)
