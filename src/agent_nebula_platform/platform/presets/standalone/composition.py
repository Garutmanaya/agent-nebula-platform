"""Standalone preset composition for Agent Studio and new Python agents."""

from __future__ import annotations

import logging
import ssl

import httpx
from fastapi import FastAPI

from agent_nebula_platform.integrations.nebula import (
    DisabledNebulaConnector,
    RestNebulaConnector,
)
from agent_nebula_platform.platform.context import RuntimeContext
from agent_nebula_platform.platform.events import NullEventSink
from agent_nebula_platform.platform.presets.common import (
    ManagedResource,
    ManagedResourcesPlugin,
)
from agent_nebula_platform.platform.presets.composition import compose_feature_plugins
from agent_nebula_platform.platform.presets.logging import create_console_event_sink
from agent_nebula_platform.platform.presets.models import (
    EmbeddedPresetOptions,
    RuntimeFeatureComponents,
)
from agent_nebula_platform.platform.runtime import AgentRuntime
from agent_nebula_platform.platform.state import JsonFileStateStore
from agent_nebula_platform.platform.tls import FileTlsContextProvider
from agent_nebula_platform.platform.transport.fastapi import runtime_lifespan

from .application import StandaloneAgent
from .settings import StandaloneRuntimeSettings


def build_standalone_agent(
    *,
    settings: StandaloneRuntimeSettings,
    components: RuntimeFeatureComponents,
) -> StandaloneAgent:
    """Build a complete opt-in agent process using built-in infrastructure.

    The preset owns only the HTTP client, connector, state store, FastAPI app,
    and Uvicorn process it creates. Business handlers, authoritative documents,
    credentials, and SDK-composed OAuth services remain caller supplied.
    """

    resolved = settings.resolve_paths()
    nebula = resolved.nebula
    client: httpx.AsyncClient | None = None
    if nebula is not None:
        tls_provider = FileTlsContextProvider(
            ca_file=nebula.ca_file,
            certificate_file=nebula.client_certificate_file,
            private_key_file=nebula.client_private_key_file,
        )
        tls_context: ssl.SSLContext = tls_provider.create_client_context()
        client = httpx.AsyncClient(
            verify=tls_context,
            timeout=httpx.Timeout(nebula.timeout_seconds),
        )
        connector = RestNebulaConnector(base_url=nebula.base_url, client=client)
    else:
        connector = DisabledNebulaConnector()

    if resolved.logging.console_enabled:
        level = getattr(logging, resolved.logging.level)
        events = create_console_event_sink(
            logger_name=resolved.logging.logger_name,
            level=level,
        )
    else:
        events = NullEventSink()

    context = RuntimeContext(
        nebula=connector,
        state_store=JsonFileStateStore(resolved.state.directory),
        events=events,
    )
    resources = ManagedResourcesPlugin(
        (ManagedResource(name="httpx.nebula", close=client.aclose),)
        if client is not None
        else ()
    )

    # FastAPI must exist before route plugins are composed. The runtime is then
    # attached through the standard lifespan hook after plugin composition,
    # avoiding deprecated startup handlers and avoiding a second runtime object.
    app = FastAPI(title=resolved.application.name)
    plugins = compose_feature_plugins(
        components=components,
        server=EmbeddedPresetOptions(
            app=app,
            enable_rest=resolved.server.enable_rest,
            enable_a2a=resolved.server.enable_a2a,
            enable_a2ui=resolved.server.enable_a2ui,
            api_prefix=resolved.server.api_prefix,
            trust_forwarded_headers=resolved.server.trust_forwarded_headers,
            forwarded_prefix_header=resolved.server.forwarded_prefix_header,
            plugins=resolved.plugins.to_runtime_settings(),
        ),
        leading_plugins=(resources,),
    )
    runtime = AgentRuntime(context=context, plugins=plugins)
    app.router.lifespan_context = runtime_lifespan(runtime)
    return StandaloneAgent(runtime=runtime, app=app, settings=resolved)
