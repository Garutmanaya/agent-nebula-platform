# A2A 1.0 client security negotiation

Step 5 interprets the remote standard Agent Card at request time. Runtime does not infer behavior from security-scheme names.

`security_requirements` are evaluated as OR choices. Every scheme inside one requirement is an AND condition; Runtime selects a requirement only when every member has a locally configured credential provider. Provider dispatch uses the official `SecurityScheme` protobuf oneof.

Supported provider families are API key, HTTP authentication, OAuth2, OpenID Connect, and mutual TLS. OAuth protocol behavior remains in `agent-nebula-sdk` through Runtime's OAuth client service. mTLS is transport identity configured by `a2aclient.conf`; it is never represented by a synthetic HTTP header.

The official A2A 1.0 interceptor API is used to apply request credentials through `ClientCallContext.service_parameters`. Header credentials work across official HTTP transports and are translated by the official gRPC transport where supported. Query/cookie API keys fail closed because the 1.0 interceptor surface does not provide a transport-neutral safe mutation point for them.

Skill-level security is not guessed from message content. Until A2A provides a deterministic selected-skill boundary, Runtime applies the Agent Card's agent-level security requirements.
