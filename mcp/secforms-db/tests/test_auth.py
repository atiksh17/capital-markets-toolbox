import os

import pytest

os.environ.setdefault("PG_DSN", "postgresql://nobody:nobody@127.0.0.1:1/none")
os.environ.setdefault("BEARER_TOKENS", "good-token")

from starlette.testclient import TestClient

from secforms_mcp.server import build_app


@pytest.fixture()
def client():
    return TestClient(build_app())


def test_healthz_no_auth(client):
    r = client.get("/healthz")
    assert r.status_code in (200, 503)


def test_mcp_without_token(client):
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401


def test_mcp_bad_token(client):
    r = client.post(
        "/mcp",
        headers={"Authorization": "Bearer wrong"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert r.status_code == 401
