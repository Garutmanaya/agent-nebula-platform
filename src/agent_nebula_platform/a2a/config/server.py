"""Agent Nebula A2A integration.

This module contains only Nebula-specific functionality layered on a2a-sdk.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from a2a.types import AgentCard
from google.protobuf.message import DecodeError
from agent_nebula_platform.platform.errors import ConfigurationError
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from collections import Counter
from collections.abc import Iterable
from a2a.types import AgentCard, InvalidParamsError, SecurityRequirement
from a2a.utils.constants import TransportProtocol
from a2a.utils.proto_utils import validate_proto_required_fields

class A2AAgentCardFactory:
    """Build and validate official ``a2a-python`` Agent Card instances."""

    def __init__(self, validator: A2AAgentCardValidator | None=None) -> None:
        """Create the factory with an injectable semantic validator."""
        self._validator = validator or A2AAgentCardValidator()

    def create(self, configuration: Mapping[str, Any]) -> AgentCard:
        """Construct one official Agent Card from a configuration mapping."""
        normalized = self._normalize_security_requirements(configuration)
        try:
            agent_card = AgentCard(**normalized)
        except (DecodeError, TypeError, ValueError) as exc:
            raise ConfigurationError('A2A Agent Card configuration does not match the A2A 1.0 model') from exc
        self._validator.validate(agent_card)
        return agent_card

    @staticmethod
    def _normalize_security_requirements(configuration: Mapping[str, Any]) -> dict[str, Any]:
        """Translate TOML scope lists into protobuf ``StringList`` mappings.

        TOML naturally expresses an A2A requirement as
        ``schemes = { oauth = ["scope"] }``.  Protobuf constructors require
        each map value to use the wrapper shape ``{"list": [...]}``.  This is
        the only configuration-specific structural adaptation performed here.
        """
        document = deepcopy(dict(configuration))

        def normalize(requirements: object) -> None:
            """Normalize one list of requirement mappings in place."""
            if not isinstance(requirements, list):
                return
            for requirement in requirements:
                if not isinstance(requirement, dict):
                    continue
                schemes = requirement.get('schemes')
                if not isinstance(schemes, dict):
                    continue
                for name, scopes in tuple(schemes.items()):
                    if isinstance(scopes, list):
                        schemes[name] = {'list': scopes}
        normalize(document.get('security_requirements'))
        skills = document.get('skills')
        if isinstance(skills, list):
            for skill in skills:
                if isinstance(skill, dict):
                    normalize(skill.get('security_requirements'))
        return document

@dataclass(frozen=True, slots=True)
class A2AServerTlsConfiguration:
    """TLS mode and material shared by HTTP and gRPC A2A server bindings."""
    enabled: bool = False
    trust_bundle: Path | None = None
    certificate_file: Path | None = None
    private_key_file: Path | None = None
    require_client_certificate: bool = False

@dataclass(frozen=True, slots=True)
class A2AListenerConfiguration:
    """Resolved network and TLS settings for one A2A server listener."""
    host: str
    port: int
    tls: A2AServerTlsConfiguration

    @property
    def certificate_file(self) -> Path | None:
        return self.tls.certificate_file

    @property
    def private_key_file(self) -> Path | None:
        return self.tls.private_key_file

    @property
    def trust_bundle_file(self) -> Path | None:
        return self.tls.trust_bundle

class A2AListenerConfigurationLoader:
    """Load A2A listener settings without exposing TOML parsing to callers."""

    def load(self, path: Path) -> A2AListenerConfiguration:
        """Parse and validate ``[server]`` and ``[server.tls]``."""
        try:
            with path.open('rb') as stream:
                document = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError(f'Invalid A2A server configuration: {path}') from exc
        server = document.get('server', {})
        if not isinstance(server, dict):
            raise ConfigurationError('a2aserver.conf [server] must be a table')
        tls_table = server.get('tls')
        if tls_table is None:
            tls_table = {'enabled': server.get('tls_certificate_file') is not None, 'trust_bundle': server.get('tls_trust_bundle_file'), 'certificate_file': server.get('tls_certificate_file'), 'private_key_file': server.get('tls_private_key_file')}
        elif not isinstance(tls_table, dict):
            raise ConfigurationError('a2aserver.conf [server.tls] must be a table')
        enabled = self._boolean(tls_table, 'enabled', default=False)
        trust_bundle = self._path(tls_table.get('trust_bundle'), path.parent)
        certificate = self._path(tls_table.get('certificate_file'), path.parent)
        private_key = self._path(tls_table.get('private_key_file'), path.parent)
        require_client_certificate = self._boolean(tls_table, 'require_client_certificate', default=False)
        if (certificate is None) != (private_key is None):
            raise ConfigurationError('A2A server TLS certificate_file and private_key_file must be configured together')
        if require_client_certificate and (not enabled or trust_bundle is None):
            raise ConfigurationError('A2A server mTLS requires TLS enabled with a trust_bundle')
        if enabled and (certificate is None or private_key is None):
            raise ConfigurationError('TLS-enabled A2A server requires certificate_file and private_key_file')
        if not enabled and any((item is not None for item in (certificate, private_key))):
            raise ConfigurationError('A2A server TLS certificate material requires [server.tls].enabled = true')
        return A2AListenerConfiguration(host=str(server.get('host', '0.0.0.0')), port=int(server.get('port', 9999)), tls=A2AServerTlsConfiguration(enabled=enabled, trust_bundle=trust_bundle, certificate_file=certificate, private_key_file=private_key, require_client_certificate=require_client_certificate))

    @staticmethod
    def _boolean(document: dict[str, object], name: str, *, default: bool) -> bool:
        value = document.get(name, default)
        if not isinstance(value, bool):
            raise ConfigurationError(f'A2A server TLS {name} must be a boolean')
        return value

    @staticmethod
    def _path(value: object, root: Path) -> Path | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError('A2A server TLS paths must be non-empty strings')
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        return candidate.resolve()

class A2AServerConfigurationLoader:
    """Load the A2A server Agent Card section from one external TOML file."""

    def load(self, path: Path) -> dict[str, Any]:
        """Read ``agent_card`` from ``path`` and return a defensive mapping copy."""
        configuration_path = path.expanduser().resolve()
        if not configuration_path.is_file():
            raise ConfigurationError('A2A server configuration file does not exist', details={'path': str(configuration_path)})
        try:
            with configuration_path.open('rb') as stream:
                document = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError('A2A server configuration file is invalid', details={'path': str(configuration_path)}) from exc
        agent_card = document.get('agent_card')
        if not isinstance(agent_card, Mapping):
            raise ConfigurationError('A2A server configuration must contain an [agent_card] section', details={'path': str(configuration_path)})
        return deepcopy(dict(agent_card))

@dataclass(frozen=True, slots=True)
class A2AServerConfiguration:
    """Resolved A2A server publication configuration.

    ``agent_card_url`` is Agent Nebula hosting configuration and is deliberately
    kept outside the official A2A ``AgentCard`` protobuf.  The Agent Card's
    ``supported_interfaces`` remain the authoritative interaction endpoints.
    """
    agent_card: AgentCard
    agent_card_url: str

    @property
    def agent_card_route(self) -> str:
        """Return the server-root route on which the public Agent Card is served."""
        return urlparse(self.agent_card_url).path

class A2AServerConfigurationService:
    """Load external A2A server configuration and the official Agent Card."""

    def __init__(self, loader: A2AServerConfigurationLoader | None=None, factory: A2AAgentCardFactory | None=None) -> None:
        """Create the service with replaceable loading and construction components."""
        self._loader = loader or A2AServerConfigurationLoader()
        self._factory = factory or A2AAgentCardFactory()

    def load(self, path: Path) -> A2AServerConfiguration:
        """Load publication settings and construct one official A2A Agent Card."""
        configuration = self._loader.load(path)
        agent_card_url = configuration.pop('url', None)
        if not isinstance(agent_card_url, str) or not agent_card_url.strip():
            raise ConfigurationError('A2A server agent_card.url must be a non-empty absolute HTTP(S) URL')
        agent_card_url = agent_card_url.strip()
        parsed = urlparse(agent_card_url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc or (not parsed.path.startswith('/')) or parsed.query or parsed.fragment:
            raise ConfigurationError('A2A server agent_card.url must be an absolute HTTP(S) URL without query or fragment', details={'value': agent_card_url})
        return A2AServerConfiguration(agent_card=self._factory.create(configuration), agent_card_url=agent_card_url)

    def load_agent_card(self, path: Path) -> AgentCard:
        """Load only the official Agent Card for compatibility with existing callers."""
        return self.load(path).agent_card

class A2AAgentCardValidator:
    """Validate official A2A requirements plus Runtime publication invariants."""

    def validate(self, agent_card: AgentCard) -> None:
        """Reject incomplete or internally inconsistent Agent Card configuration."""
        self._validate_official_required_fields(agent_card)
        self._validate_interfaces(agent_card)
        self._validate_skill_identifiers(agent_card)
        self._validate_security_schemes(agent_card)
        self._validate_requirements(agent_card.security_requirements, agent_card, location='agent_card.security_requirements')
        for index, skill in enumerate(agent_card.skills):
            self._validate_requirements(skill.security_requirements, agent_card, location=f'agent_card.skills[{index}].security_requirements')

    @staticmethod
    def _validate_official_required_fields(agent_card: AgentCard) -> None:
        """Apply required-field rules defined by the official A2A protobuf."""
        try:
            validate_proto_required_fields(agent_card)
        except InvalidParamsError as exc:
            raise ConfigurationError('A2A Agent Card is missing fields required by the A2A 1.0 model', details={'validation': exc.data}) from exc

    def _validate_interfaces(self, agent_card: AgentCard) -> None:
        """Validate interface addressing according to its official binding."""
        for index, interface in enumerate(agent_card.supported_interfaces):
            field = f'agent_card.supported_interfaces[{index}].url'
            if interface.protocol_binding in {TransportProtocol.JSONRPC, TransportProtocol.HTTP_JSON}:
                self._require_absolute_url(interface.url, field)
            elif interface.protocol_binding == TransportProtocol.GRPC:
                self._require_grpc_authority(interface.url, field)
            else:
                raise ConfigurationError('A2A Agent Card interface uses an unsupported protocol binding', details={'field': field, 'protocol_binding': interface.protocol_binding})

    @staticmethod
    def _validate_skill_identifiers(agent_card: AgentCard) -> None:
        """Reject duplicate skill identifiers that would make handler binding ambiguous."""
        duplicates = sorted((identifier for identifier, count in Counter((skill.id for skill in agent_card.skills)).items() if identifier and count > 1))
        if duplicates:
            raise ConfigurationError('A2A Agent Card skill identifiers must be unique', details={'duplicates': duplicates})

    @staticmethod
    def _validate_security_schemes(agent_card: AgentCard) -> None:
        """Require every configured security scheme to select one official A2A type."""
        for name, scheme in agent_card.security_schemes.items():
            if not name.strip():
                raise ConfigurationError('A2A security scheme name must not be blank')
            if scheme.WhichOneof('scheme') is None:
                raise ConfigurationError('A2A security scheme must configure one supported scheme type', details={'scheme': name})

    @staticmethod
    def _validate_requirements(requirements: Iterable[SecurityRequirement], agent_card: AgentCard, *, location: str) -> None:
        """Validate requirement references while preserving A2A OR-of-AND semantics."""
        known_schemes = set(agent_card.security_schemes.keys())
        for index, requirement in enumerate(requirements):
            if not requirement.schemes:
                raise ConfigurationError('A2A security requirement must reference at least one scheme', details={'location': location, 'index': index})
            unknown = sorted(set(requirement.schemes.keys()) - known_schemes)
            if unknown:
                raise ConfigurationError('A2A security requirement references undefined schemes', details={'location': location, 'index': index, 'schemes': unknown})

    @staticmethod
    def _require_absolute_url(value: str, field: str) -> None:
        """Require an absolute HTTP(S) URL without imposing deployment host values."""
        parsed = urlparse(value)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise ConfigurationError('A2A Agent Card interface URL must be an absolute HTTP(S) URL', details={'field': field, 'value': value})

    @staticmethod
    def _require_grpc_authority(value: str, field: str) -> None:
        """Require a host and port for an official gRPC interface."""
        parsed = urlparse(value if '://' in value else f'grpc://{value}')
        if parsed.scheme != 'grpc' or not parsed.hostname or parsed.port is None:
            raise ConfigurationError('A2A gRPC interface must identify a host and port', details={'field': field, 'value': value})
        if parsed.path not in {'', '/'}:
            raise ConfigurationError('A2A gRPC interface must not contain an HTTP path', details={'field': field, 'value': value})
