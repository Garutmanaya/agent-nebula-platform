"""Planning of A2A 1.0 server transports from an official Agent Card."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from a2a.types import AgentCard, AgentInterface
from a2a.utils.constants import TransportProtocol

from agent_nebula_platform.platform.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class A2AHttpInterface:
    """Describe one HTTP-hosted A2A interface to mount on FastAPI."""

    binding: str
    path: str


@dataclass(frozen=True, slots=True)
class A2AGrpcInterface:
    """Describe one gRPC listener advertised by the Agent Card."""

    host: str
    port: int

    @property
    def address(self) -> str:
        """Return the grpcio listener address."""

        return f"{self.host}:{self.port}"


@dataclass(frozen=True, slots=True)
class A2AServerInterfacePlan:
    """Hold deduplicated runtime interfaces derived from an Agent Card."""

    http: tuple[A2AHttpInterface, ...]
    grpc: tuple[A2AGrpcInterface, ...]


class A2AServerInterfacePlanner:
    """Translate advertised A2A interfaces into concrete server bindings."""

    _HTTP_BINDINGS = frozenset({TransportProtocol.JSONRPC, TransportProtocol.HTTP_JSON})

    def plan(self, agent_card: AgentCard) -> A2AServerInterfacePlan:
        """Create a fail-closed transport plan from the published interfaces."""

        http: dict[tuple[str, str], A2AHttpInterface] = {}
        grpc: dict[tuple[str, int], A2AGrpcInterface] = {}
        for interface in agent_card.supported_interfaces:
            self._require_v1(interface)
            binding = interface.protocol_binding
            if binding in self._HTTP_BINDINGS:
                planned = A2AHttpInterface(
                    binding=binding, path=self._http_path(interface)
                )
                http[(planned.binding, planned.path)] = planned
            elif binding == TransportProtocol.GRPC:
                planned_grpc = self._grpc_interface(interface)
                grpc[(planned_grpc.host, planned_grpc.port)] = planned_grpc
            else:
                raise ConfigurationError(
                    "A2A Agent Card advertises an unsupported protocol binding",
                    details={"protocol_binding": binding},
                )
        return A2AServerInterfacePlan(
            http=tuple(http.values()), grpc=tuple(grpc.values())
        )

    @staticmethod
    def _require_v1(interface: AgentInterface) -> None:
        """Reject protocol versions outside the Runtime's A2A 1.0 contract."""

        if interface.protocol_version != "1.0":
            raise ConfigurationError(
                "A2A Runtime supports protocol version 1.0 interfaces only",
                details={
                    "protocol_binding": interface.protocol_binding,
                    "protocol_version": interface.protocol_version,
                },
            )

    @staticmethod
    def _http_path(interface: AgentInterface) -> str:
        """Extract the mounted path from one absolute HTTP(S) interface URL."""

        parsed = urlparse(interface.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigurationError(
                "A2A HTTP interface must use an absolute HTTP(S) URL",
                details={"url": interface.url},
            )
        return parsed.path or "/"

    @staticmethod
    def _grpc_interface(interface: AgentInterface) -> A2AGrpcInterface:
        """Resolve either an A2A authority or grpc:// URL into a listener."""

        value = interface.url.strip()
        parsed = urlparse(value if "://" in value else f"grpc://{value}")
        if parsed.scheme != "grpc" or not parsed.hostname or parsed.port is None:
            raise ConfigurationError(
                "A2A gRPC interface must identify a host and port",
                details={"url": interface.url},
            )
        if parsed.path not in {"", "/"}:
            raise ConfigurationError(
                "A2A gRPC interface must not contain an HTTP path",
                details={"url": interface.url},
            )
        return A2AGrpcInterface(host=parsed.hostname, port=parsed.port)
