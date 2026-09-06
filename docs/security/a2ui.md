# A2UI Security Boundary

The agent controls declarative presentation intent. The trusted renderer and
Agent Runtime control execution.

Runtime validates each surface against explicit protocol, catalog, component,
and action-binding policies. It rejects executable-content fields, unsupported
versions, mixed-version streams, unresolved component references, unapproved
catalogs/components/functions, and action names without registered bindings.

An action cannot select an arbitrary URL, Python function, or transport. It
identifies an approved action name mapped during Runtime composition to one
registered skill. Protected action skills pass through the same OAuth access-token, DPoP proof, audience, method, URI, replay, and exact-scope checks used by
REST and A2A invocation.

Capability negotiation does not grant authorization. It only selects a common
protocol version and reports the intersection of renderer-supported and
runtime-approved catalog features.

The renderer must still sandbox its own component implementation and local
functions. Server-side domain validation remains mandatory.
