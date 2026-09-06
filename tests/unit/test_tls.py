import pytest

from agent_nebula_platform.platform.tls import FileTlsContextProvider


def test_tls_identity_files_must_be_paired(tmp_path):
    with pytest.raises(ValueError):
        FileTlsContextProvider(
            ca_file=tmp_path / "ca", certificate_file=tmp_path / "cert"
        )
