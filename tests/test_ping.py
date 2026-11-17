from __future__ import annotations

from fastapi.testclient import TestClient


def test_ping_returns_pong_without_auth(client: TestClient) -> None:
    response = client.get("/ping")

    assert response.status_code == 200
    assert response.text == "pong"
