from __future__ import annotations

from fastapi.testclient import TestClient


def test_hello_returns_greeting(client: TestClient) -> None:
    response = client.get("/hello")

    assert response.status_code == 200
    assert response.json() == {"greetings-from": "hello-world"}
