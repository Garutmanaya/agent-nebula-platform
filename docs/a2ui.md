# A2UI

## Purpose

The A2UI package provides declarative UI output and secure action routing without allowing an agent to deliver arbitrary executable browser content. It supports typed surfaces, protocol validation, approved component/function catalogs, actions, session state, persistence, events, and capability negotiation.

## Package layout

```text
a2ui/
├── actions/
├── data_model/
├── events/
├── persistence/
├── session/
├── surfaces/
├── models.py
├── plugin.py
├── service.py
└── validation.py
```

## Surfaces and messages

`A2UISurface` represents declarative presentation output. A skill can attach a surface to `SkillResult.ui`. A2UI messages and data parts use the Platform's supported A2UI version contract and can be serialized for compatible protocol transports.

## Validation

`A2UIComponentPolicy` and `A2UIProtocolPolicy` enforce the allowed declarative contract. The Platform can restrict components, functions, catalog identifiers, protocol versions, and action bindings. The design rejects arbitrary HTML, JavaScript, CSS, or other executable UI payloads as a presentation mechanism.

## Actions

A2UI actions are not a security bypass. `A2UIActionDispatcher` maps an approved renderer action to a configured binding and ultimately into the same skill invocation boundary used by other transports.

```text
renderer action
      ↓
A2UI action dispatcher
      ↓
approved action binding
      ↓
SkillInvocationService
      ↓
protected business operation
```

Authorization therefore remains associated with the target skill/protected-resource path rather than being implemented independently in the renderer.

## Sessions

The session package supports session snapshots, statuses, action records, task references, surface frames and surface modes. `A2UISessionService` manages session behavior. Current store implementations include in-memory and JSON-file stores.

`A2UISessionPlugin` publishes configured session services into the runtime and may use an action dispatcher when action handling is enabled.

## Surface management and data model

`A2UISurfaceManager` manages surface state/stack behavior. `A2UIDataModelService` handles declarative data-model operations. Session events provide observable state transitions without coupling the A2UI package to a specific renderer implementation.

## Capability negotiation

The A2UI model includes renderer capabilities and negotiated capabilities. Negotiation determines compatible protocol/catalog features; it does not authorize access to a business skill.

## Plugin composition

`A2UIPlugin` is enabled only when A2UI is requested and required catalog/skill components are available. A2UI session support is a separate plugin, allowing session state to be enabled independently from basic surface support.

## A2A bidirectional binding

The A2A binding carries renderer-to-agent A2UI v1.0 `action` messages as `application/a2ui+json` DataParts. Renderer state requested by `sendDataModel` is carried separately as `a2uiRendererDataModel` message metadata. v1.0 actions use the standard `action` envelope. Bidirectional RPC uses `callAgentFunction` / `agentFunctionResponse` and `callRendererFunction` / `rendererFunctionResponse` as defined by the v1.0 schemas.
