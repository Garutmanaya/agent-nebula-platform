"""Native a2a-sdk client construction with Agent Nebula configuration and security."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, ClientFactory
from a2a.types import AgentCard
from a2a.utils.constants import TransportProtocol
from .config.client import A2AClientConfiguration
from .security.client import A2AClientSecurityInterceptor

class A2AClient:
    """Resolve Agent Cards and return native ``a2a-sdk`` clients."""
    def __init__(self, configuration: A2AClientConfiguration, *, security: A2AClientSecurityInterceptor | None = None) -> None:
        self.configuration = configuration
        self.security = security

    async def resolve_agent_card(self, location: str) -> AgentCard:
        base_url, card_path = self._resolution_target(location)
        async with self._http_client() as http_client:
            return await A2ACardResolver(http_client, base_url).get_agent_card(relative_card_path=card_path)

    async def connect(self, location: str) -> Client:
        return self.create(await self.resolve_agent_card(location))

    def create(self, agent_card: AgentCard) -> Client:
        interceptors = [self.security] if self.security is not None else []
        config = ClientConfig(
            streaming=self.configuration.streaming,
            polling=self.configuration.polling,
            httpx_client=self._http_client(),
            grpc_channel_factory=self._grpc_channel_factory(),
            supported_protocol_bindings=list(self.configuration.supported_protocol_bindings),
            use_client_preference=self.configuration.use_client_preference,
            accepted_output_modes=list(self.configuration.accepted_output_modes),
        )
        return ClientFactory(config).create(agent_card, interceptors)

    def _resolution_target(self, location: str) -> tuple[str, str]:
        path = self.configuration.agent_card_path or "/.well-known/agent-card.json"
        parsed = urlsplit(location)
        if parsed.path.endswith(path):
            base_path = parsed.path[:-len(path)].rstrip("/")
            return urlunsplit((parsed.scheme, parsed.netloc, base_path, "", "")), path
        return location, path

    def _http_client(self) -> httpx.AsyncClient:
        tls = self.configuration.tls
        verify: bool | str = True
        cert = None
        if tls.trust_bundle is not None:
            verify = str(tls.trust_bundle)
        if tls.certificate_file is not None and tls.private_key_file is not None:
            cert = (str(tls.certificate_file), str(tls.private_key_file))
        return httpx.AsyncClient(verify=verify, cert=cert, timeout=self.configuration.timeout_seconds)

    def _grpc_channel_factory(self) -> Callable[[str], object] | None:
        """Create the gRPC channel factory required by the official A2A SDK."""
        if TransportProtocol.GRPC not in self.configuration.supported_protocol_bindings:
            return None
        try:
            import grpc
        except ImportError as exc:
            raise RuntimeError(
                'A2A gRPC client support requires the Platform "a2a-grpc" extra'
            ) from exc

        tls = self.configuration.tls
        if not tls.enabled:
            def create_insecure_channel(target: str) -> object:
                authority = target.removeprefix("grpc://").removeprefix("grpcs://")
                return grpc.aio.insecure_channel(authority)

            return create_insecure_channel

        root_certificates = (
            self._read_bytes(tls.trust_bundle) if tls.trust_bundle is not None else None
        )
        private_key = (
            self._read_bytes(tls.private_key_file)
            if tls.private_key_file is not None
            else None
        )
        certificate_chain = (
            self._read_bytes(tls.certificate_file)
            if tls.certificate_file is not None
            else None
        )
        credentials = grpc.ssl_channel_credentials(
            root_certificates=root_certificates,
            private_key=private_key,
            certificate_chain=certificate_chain,
        )

        def create_secure_channel(target: str) -> object:
            authority = target.removeprefix("grpcs://").removeprefix("grpc://")
            return grpc.aio.secure_channel(authority, credentials)

        return create_secure_channel

    @staticmethod
    def _read_bytes(path: Path) -> bytes:
        return path.read_bytes()
