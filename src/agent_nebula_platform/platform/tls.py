"""TLS context ports and secure default implementation."""

from __future__ import annotations

import ssl
from pathlib import Path
from typing import Protocol


class TlsContextProvider(Protocol):
    """Provide caller-controlled verified TLS contexts."""

    def create_client_context(self) -> ssl.SSLContext:
        """Return a TLS context suitable for outbound verified connections."""
        ...


class FileTlsContextProvider:
    """Create peer-verifying contexts from explicit trust and optional mTLS files."""

    def __init__(
        self,
        *,
        ca_file: Path,
        certificate_file: Path | None = None,
        private_key_file: Path | None = None,
    ) -> None:
        if (certificate_file is None) != (private_key_file is None):
            raise ValueError("Certificate and private key must be supplied together")
        self._ca = ca_file
        self._cert = certificate_file
        self._key = private_key_file

    def create_client_context(self) -> ssl.SSLContext:
        """Return a context that never disables hostname or peer verification."""
        context = ssl.create_default_context(cafile=str(self._ca))
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        if self._cert is not None:
            context.load_cert_chain(str(self._cert), str(self._key))
        return context
