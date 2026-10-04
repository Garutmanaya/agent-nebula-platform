"""Official A2A 1.0 Runtime integration."""

from .client.client_adapter import A2AClientAdapter
from .client.client_configuration import (
    A2AClientConfiguration,
    A2AClientConfigurationLoader,
    A2AClientTlsConfiguration,
)
from .client.client_credentials import (
    A2AApiKeyCredentialProvider,
    A2AHttpCredentialProvider,
    A2AMutualTlsCredentialProvider,
    A2AOAuth2CredentialProvider,
    A2AOidcCredentialProvider,
    A2AStaticCredential,
)
from .client.client_security import (
    A2AClientCredential,
    A2AClientCredentialProvider,
    A2AClientSecurityInterceptor,
    A2AClientSecurityRequest,
    A2AClientSecurityResolver,
)
from .client.client_service import A2AClientServiceFactory
from .security.factory import A2AServerSecurityComposition, A2AServerSecurityFactory
from .security.oauth_security import A2AOAuth2ProtectedResourceAuthenticator
from .security.security import (
    A2AAuthenticatedPrincipal,
    A2ASecurityRequest,
    A2ASecuritySchemeAuthenticator,
    A2AServerSecurityService,
)
from .server.server_adapter import A2AServerAdapter
from .server.server_interfaces import A2AServerInterfacePlan, A2AServerInterfacePlanner

__all__ = [
    "A2AApiKeyCredentialProvider",
    "A2AAuthenticatedPrincipal",
    "A2AClientAdapter",
    "A2AClientConfiguration",
    "A2AClientConfigurationLoader",
    "A2AClientCredential",
    "A2AClientCredentialProvider",
    "A2AClientSecurityInterceptor",
    "A2AClientSecurityRequest",
    "A2AClientSecurityResolver",
    "A2AClientServiceFactory",
    "A2AClientTlsConfiguration",
    "A2AHttpCredentialProvider",
    "A2AMutualTlsCredentialProvider",
    "A2AOAuth2CredentialProvider",
    "A2AOAuth2ProtectedResourceAuthenticator",
    "A2AOidcCredentialProvider",
    "A2ASecurityRequest",
    "A2AServerSecurityComposition",
    "A2AServerSecurityFactory",
    "A2ASecuritySchemeAuthenticator",
    "A2AServerAdapter",
    "A2AServerInterfacePlan",
    "A2AServerInterfacePlanner",
    "A2AServerSecurityService",
    "A2AStaticCredential",
]
