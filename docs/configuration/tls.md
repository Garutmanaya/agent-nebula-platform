# TLS Configuration

TLS peer and hostname verification remain enabled. The runtime has no `verify=False` path.

Standalone mode requires:

- explicit Agent Nebula CA/trust material;
- optional client certificate and private key when configured;
- explicit HTTPS server certificate and private key for the managed listener.

The file TLS provider validates certificate/key pairing and builds standard SSL contexts. HTTPX receives a verified SSL context rather than Pydantic URL or path objects.

Production deployments are responsible for certificate provisioning, rotation, filesystem permissions, and trust-bundle lifecycle.
