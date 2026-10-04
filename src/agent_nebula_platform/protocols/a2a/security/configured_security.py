"""Configuration-driven validators for standard A2A server security schemes."""
from __future__ import annotations

import hmac
import tomllib
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from agent_nebula_sdk.core.encoding import encode_base64url
from agent_nebula_sdk.core.errors import ProtocolValidationError
from agent_nebula_sdk.jose.jwk.models import RsaPublicJwk
from agent_nebula_sdk.security import (
    ApiKeyAuthenticator, AuthenticatedIdentity, HttpAuthAuthenticator,
    MtlsClientCertificateAuthenticator, MtlsTrustPolicy, OidcJwtAuthenticator,
)

from agent_nebula_platform.platform.errors import ConfigurationError
from .standard_security import (
    A2AApiKeyAuthenticator, A2AHttpAuthAuthenticator, A2AMutualTlsAuthenticator,
    A2AOidcValidationContext, A2AOpenIdConnectAuthenticator,
)


@dataclass(frozen=True, slots=True)
class _StaticVerifier:
    expected: str
    subject: str
    def verify(self, credential: str) -> AuthenticatedIdentity:
        if not hmac.compare_digest(credential, self.expected):
            raise ProtocolValidationError("credential validation failed", code="invalid_credential")
        return AuthenticatedIdentity(subject=self.subject, attributes={})


@dataclass(frozen=True, slots=True)
class _StaticOidcKeyResolver:
    key: RsaPublicJwk
    issuer: str
    def resolve(self, *, issuer: str, key_id: str, algorithm: str):
        if issuer != self.issuer or key_id != self.key.kid or algorithm != self.key.alg:
            raise ProtocolValidationError("OIDC signing key is not trusted", code="invalid_oidc_key")
        return self.key


class A2AConfiguredSecurityLoader:
    """Build Platform A2A security adapters from private local server configuration.

    AGENT NEBULA SECURITY: ``[security]`` is deliberately outside ``[agent_card]``.
    AgentCard security metadata is public A2A contract data; verifier secrets and
    trust policy are local implementation details and must never be published.
    """
    def load(
        self, path: Path, *, mtls_transport_enforced: bool = False
    ) -> tuple[object, ...]:
        try:
            with path.open('rb') as stream:
                document=tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigurationError(f"Invalid A2A server configuration: {path}") from exc
        security=document.get('security', {})
        if not isinstance(security, dict):
            raise ConfigurationError('a2aserver.conf [security] must be a table')
        root=path.resolve().parent
        result=[]

        api={}
        for name, cfg in self._named(security, 'api_key').items():
            api[name]=ApiKeyAuthenticator(_StaticVerifier(self._secret(cfg, root), self._subject(cfg)))
        if api: result.append(A2AApiKeyAuthenticator(api))

        http={}
        for name, cfg in self._named(security, 'http_auth').items():
            scheme=self._string(cfg, 'scheme')
            http[name]=HttpAuthAuthenticator(scheme=scheme, verifier=_StaticVerifier(self._secret(cfg, root), self._subject(cfg)))
        if http: result.append(A2AHttpAuthAuthenticator(http))

        oidc={}
        for name, cfg in self._named(security, 'oidc').items():
            issuer=self._string(cfg,'issuer'); discovery=self._string(cfg,'discovery_url')
            audiences=tuple(self._strings(cfg,'audiences'))
            if not audiences: raise ConfigurationError('OIDC audiences must not be empty')
            cert=self._path(cfg,'verification_certificate_file',root)
            kid=self._string(cfg,'key_id'); algorithm=self._string(cfg,'algorithm')
            certificate=x509.load_pem_x509_certificate(cert.read_bytes())
            public=certificate.public_key()
            if not isinstance(public, rsa.RSAPublicKey):
                raise ConfigurationError('Configured OIDC verification certificate must contain an RSA public key')
            numbers=public.public_numbers()
            jwk=RsaPublicJwk(kty='RSA', kid=kid, use='sig', alg=algorithm,
                n=self._uint(numbers.n), e=self._uint(numbers.e))
            authenticator=OidcJwtAuthenticator(key_resolver=_StaticOidcKeyResolver(jwk,issuer), allowed_algorithms=(algorithm,))
            oidc[name]=A2AOidcValidationContext(authenticator=authenticator,issuer=issuer,audiences=audiences,discovery_url=discovery)
        if oidc: result.append(A2AOpenIdConnectAuthenticator(oidc))

        mtls=security.get('mtls')
        if mtls is not None:
            if not isinstance(mtls,dict): raise ConfigurationError('[security.mtls] must be a table')
            trust=self._path(mtls,'trust_bundle',root)
            policy=MtlsTrustPolicy.from_pem(trust_bundle_pem=trust.read_bytes())
            result.append(A2AMutualTlsAuthenticator(
                MtlsClientCertificateAuthenticator(policy),
                transport_enforced=mtls_transport_enforced,
            ))
        return tuple(result)

    @staticmethod
    def _uint(value: int) -> str:
        return encode_base64url(value.to_bytes((value.bit_length() + 7) // 8, "big"))
    @staticmethod
    def _named(doc,name):
        value=doc.get(name,{})
        if not isinstance(value,dict): raise ConfigurationError(f'[security.{name}] must be a table')
        for k,v in value.items():
            if not isinstance(v,dict): raise ConfigurationError(f'[security.{name}.{k}] must be a table')
        return value
    @staticmethod
    def _string(doc,name):
        value=doc.get(name)
        if not isinstance(value,str) or not value.strip(): raise ConfigurationError(f'security {name} must be a non-empty string')
        return value.strip()
    @classmethod
    def _strings(cls,doc,name):
        value=doc.get(name)
        if not isinstance(value,list) or any(not isinstance(x,str) or not x.strip() for x in value): raise ConfigurationError(f'security {name} must be a string list')
        return [x.strip() for x in value]
    @classmethod
    def _path(cls,doc,name,root):
        value=Path(cls._string(doc,name)).expanduser(); value=value if value.is_absolute() else root/value
        value=value.resolve()
        if not value.is_file(): raise ConfigurationError(f'security file does not exist: {value}')
        return value
    @classmethod
    def _secret(cls,doc,root):
        value=cls._path(doc,'secret_file',root).read_text(encoding='utf-8').strip()
        if not value: raise ConfigurationError('security credential file is empty')
        return value
    @staticmethod
    def _subject(doc):
        value=doc.get('subject','a2a-client')
        if not isinstance(value,str) or not value.strip(): raise ConfigurationError('security subject must be non-empty')
        return value.strip()
