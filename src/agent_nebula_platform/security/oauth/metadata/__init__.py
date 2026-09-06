"""Protected-resource metadata builders and publication helpers."""
from .authorization_server import (
    AuthorizationServerConnection,
    AuthorizationServerMetadata,
    AuthorizationServerMetadataResolver,
)
from .builders import ProtectedResourceMetadataBuilder
from .factory import ProtectedResourceMetadataFactory
from .metadata import (
    ProtectedResourceMetadataDocument,
    ProtectedResourceMetadataProvider,
    StaticProtectedResourceMetadataProvider,
)

__all__ = [
    "AuthorizationServerConnection",
    "AuthorizationServerMetadata",
    "AuthorizationServerMetadataResolver",
    "ProtectedResourceMetadataBuilder",
    "ProtectedResourceMetadataDocument",
    "ProtectedResourceMetadataFactory",
    "ProtectedResourceMetadataProvider",
    "StaticProtectedResourceMetadataProvider",
]
