from __future__ import annotations

from fastapi.testclient import TestClient


def test_version_returns_the_current_version(client: TestClient) -> None:
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": "0.1.0"}
