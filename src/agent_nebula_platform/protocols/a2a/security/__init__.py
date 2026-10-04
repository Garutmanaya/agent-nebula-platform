"""A2A-specific security interpretation and authentication integration."""

from .context import A2ASecurityServerCallContextBuilder
from .configured_security import A2AConfiguredSecurityLoader
from .factory import A2AServerSecurityComposition, A2AServerSecurityFactory
from .oauth_security import A2AOAuth2ProtectedResourceAuthenticator
from .protected_resource import (
    A2AProtectedResourceComposition,
    A2AProtectedResourceFactory,
)
from .security import (
    A2AAuthenticatedPrincipal,
    A2ASecurityRequest,
    A2ASecuritySchemeAuthenticator,
    A2AServerSecurityService,
)

__all__ = [
    "A2AAuthenticatedPrincipal",
    "A2ASecurityServerCallContextBuilder",
    "A2AConfiguredSecurityLoader",
    "A2AOAuth2ProtectedResourceAuthenticator",
    "A2AProtectedResourceComposition",
    "A2AProtectedResourceFactory",
    "A2ASecurityRequest",
    "A2AServerSecurityComposition",
    "A2AServerSecurityFactory",
    "A2ASecuritySchemeAuthenticator",
    "A2AServerSecurityService",
]
