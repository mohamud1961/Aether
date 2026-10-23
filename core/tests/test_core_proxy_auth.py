"""Modal proxy-auth headers for a Flint endpoint: unset, valid, malformed, and sent by the client."""

import pytest

from aether.core import harbor_agent as adapter
from aether.core.strict import PROXY_AUTH_ENV, proxy_headers


def _provider_env(monkeypatch):
    for name in (adapter.ENDPOINT_ENV, adapter.KEY_ENV, adapter.DEPLOYMENT_ENV):
        monkeypatch.setenv(
            name, "https://example.invalid" if name == adapter.ENDPOINT_ENV else "x"
        )


def test_unset_means_no_proxy_headers(monkeypatch):
    monkeypatch.delenv(PROXY_AUTH_ENV, raising=False)
    assert proxy_headers({}) == {}


def test_valid_file_gives_both_headers(tmp_path):
    auth = tmp_path / "flint_proxy_auth"
    auth.write_text("tok-id-123\ntok-secret-456\n")
    assert proxy_headers({PROXY_AUTH_ENV: str(auth)}) == {
        "Modal-Key": "tok-id-123",
        "Modal-Secret": "tok-secret-456",
    }


def test_malformed_file_is_refused_without_echoing_the_secret(tmp_path):
    secret = "SUPER-SECRET-VALUE-789"
    auth = tmp_path / "flint_proxy_auth"
    auth.write_text(f"only-one-line-{secret}\n\n")
    with pytest.raises(ValueError) as caught:
        proxy_headers({PROXY_AUTH_ENV: str(auth)})
    assert PROXY_AUTH_ENV in str(caught.value)
    assert secret not in str(caught.value)


def test_missing_file_is_refused_and_names_the_variable(tmp_path):
    missing = tmp_path / "does_not_exist"
    with pytest.raises(ValueError) as caught:
        proxy_headers({PROXY_AUTH_ENV: str(missing)})
    assert PROXY_AUTH_ENV in str(caught.value)


def test_client_receives_the_headers(monkeypatch, tmp_path):
    _provider_env(monkeypatch)
    auth = tmp_path / "flint_proxy_auth"
    auth.write_text("tok-id-123\ntok-secret-456\n")
    monkeypatch.setenv(PROXY_AUTH_ENV, str(auth))
    headers = adapter.build_provider()._client.default_headers
    assert headers["Modal-Key"] == "tok-id-123"
    assert headers["Modal-Secret"] == "tok-secret-456"


def test_client_sends_no_proxy_headers_when_unset(monkeypatch):
    _provider_env(monkeypatch)
    monkeypatch.delenv(PROXY_AUTH_ENV, raising=False)
    headers = adapter.build_provider()._client.default_headers
    assert "Modal-Key" not in headers and "Modal-Secret" not in headers
