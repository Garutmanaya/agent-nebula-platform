# A2UI Plugin

The A2UI capability connects declarative UI documents to Runtime skills. It is
not a renderer and does not contain domain-specific UI.

## Runtime responsibilities

- preserve complete A2UI message documents;
- enforce the configured supported and preferred versions;
- expose renderer capabilities and negotiate a common version;
- validate create, update, and delete ordering and surface ownership;
- enforce caller-approved catalog identifiers and component names;
- validate component references across the complete surface stream;
- reject raw HTML, scripts, JavaScript, `srcdoc`, and
  `dangerouslySetInnerHTML`;
- validate that declared action names have registered bindings;
- validate at startup that every binding targets a registered Runtime skill;
- serialize message arrays as `application/a2ui+json` A2A DataParts;
- route protected actions through OAuth, DPoP, and exact-scope enforcement.

## Renderer responsibilities

- implement the approved native component catalog;
- apply visual styling and accessibility behavior;
- keep browser/session state;
- sandbox explicitly approved renderer-local functions;
- submit action envelopes without changing the selected skill or target URL.

## Capability endpoints

When A2UI and the FastAPI adapter are enabled:

```text
GET  /api/v1/a2ui/capabilities
POST /api/v1/a2ui/negotiate
POST /api/v1/a2ui/actions
```

The capability response exposes only public protocol information: MIME type,
versions, component names, approved renderer-local functions, and action names.
It never exposes Python handlers, credentials, scopes, tokens, or private
configuration.

## Composition

```python
from agent_runtime.a2ui import A2UIActionBinding
from agent_runtime.presets import RuntimeFeatureComponents

components = RuntimeFeatureComponents.create(
    skill_definitions=skills,
    a2ui_allowed_components=("Column", "Text", "Button", "Card"),
    a2ui_allowed_catalog_ids=("urn:example:a2ui:travel",),
    a2ui_supported_versions=("v0.9.1",),
    a2ui_preferred_version="v0.9.1",
    a2ui_action_bindings=(
        A2UIActionBinding(
            action_name="select_flight",
            skill_id="flight.select",
        ),
    ),
)
```

A2UI is presentation, not authorization. See
[A2UI security](../security/a2ui.md) and the
[A2UI example](../examples/a2ui.md).
