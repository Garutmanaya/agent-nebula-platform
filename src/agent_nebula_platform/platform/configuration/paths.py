"""Central path ownership and containment rules for Runtime applications."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_nebula_platform.platform.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class RuntimePathResolver:
    """Resolve application-owned and product-shared paths without ambiguity.

    ``runtime_root`` owns instance-local files such as service certificates,
    logs, and generated configuration. ``product_root`` owns resources and
    externally persisted state shared by applications in one product
    installation, such as trust bundles, common credentials, and recoverable
    onboarding identity.
    """

    runtime_root: Path
    product_root: Path

    @classmethod
    def create(
        cls, *, runtime_root: Path, product_root: Path | None = None
    ) -> RuntimePathResolver:
        """Create a resolver from configured roots after canonicalization."""

        runtime = runtime_root.expanduser().resolve()
        product = (product_root or runtime).expanduser().resolve()
        return cls(runtime_root=runtime, product_root=product)

    def runtime_path(self, path: Path | None) -> Path | None:
        """Resolve a path that must remain inside the application runtime root."""

        return self._resolve(
            path, base=self.runtime_root, allowed=(self.runtime_root,), kind="runtime"
        )

    def shared_path(self, path: Path | None) -> Path | None:
        """Resolve a path allowed beneath either product root or runtime root."""

        return self._resolve(
            path,
            base=self.product_root,
            allowed=(self.product_root, self.runtime_root),
            kind="shared",
        )

    @staticmethod
    def _resolve(
        path: Path | None,
        *,
        base: Path,
        allowed: tuple[Path, ...],
        kind: str,
    ) -> Path | None:
        """Resolve one path and reject traversal outside its ownership roots."""

        if path is None:
            return None
        expanded = path.expanduser()
        candidate = (
            expanded.resolve()
            if expanded.is_absolute()
            else (base / expanded).resolve()
        )
        if not any(candidate == root or root in candidate.parents for root in allowed):
            raise ConfigurationError(
                f"Configured {kind} path escapes configured {kind} root"
            )
        return candidate
