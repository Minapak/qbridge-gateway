"""
v1.6.2 — /gateway/qlogos/{path} credential separation.

The inbound ``Authorization`` (gateway API key) must never reach Q-Logos;
the user's JWT travels in ``X-Upstream-Authorization`` and becomes the
upstream ``Authorization``. ``X-PQC-*`` headers are not relayed.
"""

import pytest
import httpx
# Bind the REAL client classes before any test monkeypatches httpx.AsyncClient.
from httpx import AsyncClient as _RealAsyncClient, ASGITransport as _RealASGITransport

import gateway_agent.server as _server_mod
from gateway_agent.server import GatewayServer, _qlogos_upstream_headers, UPSTREAM_AUTH_HEADER

GW_KEY = "gw-secret-key-123"
USER_JWT = "Bearer eyJhbGciOiJIUzI1NiJ9.USER.JWT"


class _FakeResponse:
    def __init__(self, status_code=200, body=None, headers=None):
        self.status_code = status_code
        self._body = body if body is not None else {"ok": True}
        self.headers = headers or {"content-type": "application/json"}
        self.text = "{}"

    def json(self):
        return self._body


class _FakeAsyncClient:
    """Records the single upstream call the proxy makes."""
    calls = []

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def request(self, method, url, params=None, headers=None, content=None):
        _FakeAsyncClient.calls.append({
            "method": method, "url": url, "params": params,
            "headers": {k.lower(): v for k, v in (headers or {}).items()},
            "content": content,
        })
        return _FakeResponse()


@pytest.fixture
def upstream(monkeypatch):
    _FakeAsyncClient.calls = []
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient.calls


@pytest.fixture
def prod_client(monkeypatch):
    """Production-like gateway: key set, ENVIRONMENT=production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(_server_mod, "_GATEWAY_API_KEY", GW_KEY)
    return _RealAsyncClient(transport=_RealASGITransport(app=GatewayServer().app), base_url="http://testserver")


# ── pure helper ───────────────────────────────────────────────────────────

def test_helper_drops_inbound_authorization_and_promotes_upstream_header():
    out = _qlogos_upstream_headers({
        "authorization": f"Bearer {GW_KEY}",
        UPSTREAM_AUTH_HEADER: USER_JWT,
        "content-type": "application/json",
        "accept-language": "ko",
        "x-pqc-algorithm": "ML-KEM-768",
        "x-pqc-standard": "FIPS-203",
        "x-forwarded-for": "1.2.3.4",
    })
    assert out == {"content-type": "application/json", "accept-language": "ko", "authorization": USER_JWT}


def test_helper_no_upstream_header_means_no_authorization_at_all():
    out = _qlogos_upstream_headers({"authorization": f"Bearer {GW_KEY}", "content-type": "text/plain"})
    assert out == {"content-type": "text/plain"}


# ── end-to-end through the middleware ─────────────────────────────────────

@pytest.mark.asyncio
async def test_gateway_key_never_forwarded_user_jwt_becomes_upstream_auth(prod_client, upstream):
    r = await prod_client.post(
        "/gateway/qlogos/orders",
        headers={
            "Authorization": f"Bearer {GW_KEY}",
            "X-Upstream-Authorization": USER_JWT,
            "Content-Type": "application/json",
            "Accept-Language": "ko",
            "X-PQC-Algorithm": "ML-KEM-768",
            "X-PQC-Standard": "FIPS-203",
        },
        content=b'{"a":1}',
    )
    assert r.status_code == 200, r.text
    assert len(upstream) == 1
    call = upstream[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/v1/orders")
    assert call["content"] == b'{"a":1}'
    h = call["headers"]
    assert h["authorization"] == USER_JWT
    assert "x-upstream-authorization" not in h
    assert "x-pqc-algorithm" not in h and "x-pqc-standard" not in h
    assert GW_KEY not in " ".join(f"{k}={v}" for k, v in h.items())


@pytest.mark.asyncio
async def test_without_upstream_header_upstream_gets_no_authorization(prod_client, upstream):
    r = await prod_client.get(
        "/gateway/qlogos/routes?limit=5",
        headers={"Authorization": f"Bearer {GW_KEY}"},
    )
    assert r.status_code == 200, r.text
    h = upstream[0]["headers"]
    assert "authorization" not in h
    assert upstream[0]["params"] == {"limit": "5"}


@pytest.mark.asyncio
async def test_gateway_auth_still_enforced_before_proxy(prod_client, upstream):
    r = await prod_client.get("/gateway/qlogos/routes", headers={"X-Upstream-Authorization": USER_JWT})
    assert r.status_code == 401
    r = await prod_client.get("/gateway/qlogos/routes", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403
    assert upstream == []


@pytest.mark.asyncio
async def test_dev_mode_inbound_authorization_still_not_forwarded(monkeypatch, upstream):
    """Even with auth disabled (dev), a bare Authorization is not relayed —
    the upstream identity must be explicit."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setattr(_server_mod, "_GATEWAY_API_KEY", "")
    client = _RealAsyncClient(transport=_RealASGITransport(app=GatewayServer().app), base_url="http://testserver")
    r = await client.get("/gateway/qlogos/routes", headers={"Authorization": "Bearer some-jwt"})
    assert r.status_code == 200
    assert "authorization" not in upstream[0]["headers"]


def test_cors_allows_upstream_authorization_header():
    srv = GatewayServer()
    cors = [m for m in srv.app.user_middleware if m.cls.__name__ == "CORSMiddleware"]
    assert cors, "CORSMiddleware not registered"
    allow = [h.lower() for h in cors[0].kwargs.get("allow_headers", [])]
    assert "x-upstream-authorization" in allow


def test_version_is_1_6_3():
    import gateway_agent
    assert gateway_agent.__version__ == "1.6.3"
