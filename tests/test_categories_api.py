from __future__ import annotations

from fastapi.testclient import TestClient

from tests.support import AUTH


def test_categories_is_empty_when_there_are_no_items(client: TestClient) -> None:
    response = client.get("/categories")

    assert response.status_code == 200
    assert response.json() == []


def test_categories_are_distinct_and_sorted(client: TestClient) -> None:
    for sku, category in [("C-300", "tools"), ("A-100", "parts"), ("B-200", "tools")]:
        client.post(
            "/items",
            json={"sku": sku, "name": sku, "category": category, "unit_price_pence": 1},
            headers=AUTH,
        )

    response = client.get("/categories")

    assert response.status_code == 200
    assert response.json() == ["parts", "tools"]
