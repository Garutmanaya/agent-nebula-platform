"""Resolve the externally visible HTTP request target."""

from __future__ import annotations

from fastapi import Request


class RequestTargetResolver:
    """Build the absolute URI used for DPoP ``htu`` validation."""

    def __init__(
        self,
        *,
        trust_forwarded_headers: bool = False,
        forwarded_prefix_header: str = "X-Forwarded-Prefix",
    ) -> None:
        self._trust_forwarded_headers = trust_forwarded_headers
        self._forwarded_prefix_header = forwarded_prefix_header.lower()

    def resolve(self, request: Request) -> str:
        """Return the direct or trusted proxy-visible request URI."""

        if not self._trust_forwarded_headers:
            return str(request.url)

        proto = self._first(request.headers.get("x-forwarded-proto"))
        host = self._first(request.headers.get("x-forwarded-host"))
        if not proto or not host:
            return str(request.url)

        port = self._first(request.headers.get("x-forwarded-port"))
        prefix = self._first(request.headers.get(self._forwarded_prefix_header))

        authority = host
        if port and not self._has_explicit_port(host):
            is_default = (proto == "https" and port == "443") or (
                proto == "http" and port == "80"
            )
            if not is_default:
                authority = f"{host}:{port}"

        path = request.url.path
        if prefix:
            normalized_prefix = "/" + prefix.strip("/")
            if path != normalized_prefix and not path.startswith(
                normalized_prefix + "/"
            ):
                path = normalized_prefix + path

        target = f"{proto}://{authority}{path}"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return target

    @staticmethod
    def _first(value: str | None) -> str | None:
        if value is None:
            return None
        result = value.split(",", maxsplit=1)[0].strip()
        return result or None

    @staticmethod
    def _has_explicit_port(authority: str) -> bool:
        if authority.startswith("["):
            return "]:" in authority
        return authority.count(":") == 1
