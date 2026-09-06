"""Opt-in embedded and standalone Agent Runtime composition presets."""

from .application import (
    RuntimeA2UISessionSettings,
    RuntimeApplication,
    RuntimeApplicationBuilder,
    RuntimeApplicationServices,
    RuntimeApplicationSettings,
    RuntimeOAuthClientSettings,
    RuntimeOnboardingSettings,
    RuntimeProtectedResourceSettings,
    RuntimeRoleProfile,
)
from .embedded import build_embedded_runtime
from .models import (
    EmbeddedPresetOptions,
    RuntimeFeatureComponents,
    RuntimePluginSettings,
)
from .standalone import (
    StandaloneAgent,
    StandalonePluginSettings,
    StandaloneRuntimeSettings,
    build_standalone_agent,
)

__all__ = [
    "EmbeddedPresetOptions",
    "RuntimeA2UISessionSettings",
    "RuntimeApplication",
    "RuntimeApplicationBuilder",
    "RuntimeApplicationServices",
    "RuntimeApplicationSettings",
    "RuntimeFeatureComponents",
    "RuntimeOAuthClientSettings",
    "RuntimeOnboardingSettings",
    "RuntimePluginSettings",
    "RuntimeProtectedResourceSettings",
    "RuntimeRoleProfile",
    "StandaloneAgent",
    "StandalonePluginSettings",
    "StandaloneRuntimeSettings",
    "build_embedded_runtime",
    "build_standalone_agent",
]
