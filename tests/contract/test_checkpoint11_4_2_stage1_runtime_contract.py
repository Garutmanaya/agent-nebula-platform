"""Checkpoint 11.4.2 Stage 1 architectural source contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_role_neutral_runtime_settings_are_public() -> None:
    """Require optional client/provider settings and role profile exports."""

    source = (ROOT / "src/agent_nebula_platform/presets/application.py").read_text(
        encoding="utf-8"
    )
    exports = (ROOT / "src/agent_nebula_platform/presets/__init__.py").read_text(
        encoding="utf-8"
    )
    assert "oauth_client: RuntimeOAuthClientSettings | None = None" in source
    assert (
        "protected_resource: RuntimeProtectedResourceSettings | None = None" in source
    )
    assert "class RuntimeRoleProfile" in source
    assert '"RuntimeProtectedResourceSettings"' in exports
    assert '"RuntimeRoleProfile"' in exports


def test_runtime_owns_provider_security_composition() -> None:
    """Require provider SDK composition and cleanup inside Agent Runtime."""

    factory = (
        ROOT / "src/agent_nebula_platform/oauth/protected_resource/factory.py"
    ).read_text(encoding="utf-8")
    application = (ROOT / "src/agent_nebula_platform/presets/application.py").read_text(
        encoding="utf-8"
    )
    assert "JwtAccessTokenValidator" in factory
    assert "DpopProofValidator" in factory
    assert "RemoteJwksResolver" in factory
    assert "ProtectedResourceRuntimeFactory().build" in application
    assert 'name="oauth.protected_resource.transport"' in application


def test_runtime_centralizes_path_ownership() -> None:
    """Require runtime-root and product-root resolution in one component."""

    source = (ROOT / "src/agent_nebula_platform/configuration/paths.py").read_text(
        encoding="utf-8"
    )
    settings = (
        ROOT / "src/agent_nebula_platform/presets/standalone/settings.py"
    ).read_text(encoding="utf-8")
    assert "class RuntimePathResolver" in source
    assert "def runtime_path" in source
    assert "def shared_path" in source
    assert "product_root: Path | None = None" in settings
    assert "resolver.shared_path(self.nebula.ca_file)" in settings


def test_authoritative_requirements_document_exists() -> None:
    """Require the shared future-development contract in Agent Runtime."""

    document = ROOT / "docs/AGENT_ECOSYSTEM_DESIGN_AND_IMPLEMENTATION_REQUIREMENTS.md"
    text = document.read_text(encoding="utf-8")
    assert "Agent Studio must not import `agent_nebula_sdk` directly" in text
    assert "Runtime owns every `runtime.*` section" in text
    assert "RuntimePathResolver" in text
