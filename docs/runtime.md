# Runtime paths and filesystem isolation

`RuntimePathResolver` in `src/agent_nebula_platform/platform/configuration/paths.py` manages configured filesystem roots. `runtime_path()` checks containment within the configured runtime root; `shared_path()` accepts paths under either the runtime or product root. Callers can supply those roots. This is **not** a process-wide `/run/agent-nebula` allowlist.

For deployments that require runtime writes only under `/run/agent-nebula`:

1. Mount `/run/agent-nebula` as the writable runtime volume and use it as the configured runtime root.
2. Run as a non-root user with only the required directory ownership and permissions.
3. Mount the rest of the application filesystem read-only wherever practical, including product configuration and certificates.
4. Validate the effective container or OS filesystem permissions independently of Python path validation.

Read-only access to system libraries, installed Python packages, and configuration is normally necessary. A blanket prohibition on **all** access outside `/run/agent-nebula` would prevent normal Python startup; distinguish prohibited **writes** from necessary read-only dependencies. The strict deployment policy is an operational requirement, not a security guarantee implemented by the current resolver.
