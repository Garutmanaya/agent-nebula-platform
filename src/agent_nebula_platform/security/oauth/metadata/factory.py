"""Generic RFC 9728 Protected Resource Metadata construction for Platform."""

from __future__ import annotations

from collections.abc import Iterable

from .authorization_server import AuthorizationServerMetadata
from .builders import ProtectedResourceMetadataBuilder
from .metadata import StaticProtectedResourceMetadataProvider


class ProtectedResourceMetadataFactory:
    """Create protected-resource metadata from protocol-neutral Platform inputs."""

    def create(
        self,
        *,
        resource: str,
        resource_name: str,
        authorization_server: AuthorizationServerMetadata,
        scopes: Iterable[str],
        dpop_algorithms: tuple[str, ...],
    ) -> StaticProtectedResourceMetadataProvider:
        """Build validated RFC 9728 metadata using the existing SDK-backed builder."""

        document = (
            ProtectedResourceMetadataBuilder()
            .resource(resource.rstrip("/"))
            .authorization_servers((authorization_server.issuer,))
            .scopes_supported(tuple(dict.fromkeys(scopes)))
            .bearer_methods(("header",))
            .dpop(required=True, algorithms=dpop_algorithms)
            .details(resource_name=resource_name)
            .build()
        )
        return StaticProtectedResourceMetadataProvider(document.copy_document())
