# Third-Party Integration Checklist

- [ ] Decide embedded, standalone, or custom composition mode.
- [ ] Supply verified TLS trust and service certificates.
- [ ] Keep secrets file-backed or host-managed.
- [ ] Supply complete Agent Card and Protected Resource Metadata.
- [ ] Validate skill `required_scopes` against `scopes_supported`.
- [ ] Compose OAuth services through `agent-nebula-sdk`.
- [ ] Select only required runtime plugins.
- [ ] Integrate runtime lifecycle with host startup/shutdown.
- [ ] Confirm no route collisions.
- [ ] Confirm tokens, assertions, keys, and headers are not logged.
- [ ] Add positive and negative OAuth/DPoP tests.
- [ ] Add lifecycle rollback and graceful-shutdown tests.
- [ ] Treat local runtime state as cache, not registration authority.
- [ ] Document custom ports and adapters.
