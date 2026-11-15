from __future__ import annotations

from fastapi.testclient import TestClient

from tests.support import AUTH


def add_item(client: TestClient, sku: str, quantity: int) -> None:
    response = client.post(
        "/items",
        json={"sku": sku, "name": sku, "quantity": quantity, "unit_price_pence": 1},
        headers=AUTH,
    )
    assert response.status_code == 201


def quantity(client: TestClient, sku: str) -> int:
    return client.get(f"/items/{sku}").json()["quantity"]


def test_batch_applies_every_adjustment_and_returns_the_items(client: TestClient) -> None:
    add_item(client, "AAA-1", 5)
    add_item(client, "BBB-1", 5)

    response = client.post(
        "/adjustments",
        json=[
            {"sku": "AAA-1", "delta": 3, "reason": "delivery"},
            {"sku": "BBB-1", "delta": -5, "reason": "order"},
        ],
        headers=AUTH,
    )

    assert response.status_code == 200
    assert [(i["sku"], i["quantity"]) for i in response.json()] == [("AAA-1", 8), ("BBB-1", 0)]
    assert quantity(client, "AAA-1") == 8
    assert quantity(client, "BBB-1") == 0


def test_unknown_sku_is_404_names_it_and_changes_nothing(client: TestClient) -> None:
    add_item(client, "AAA-1", 5)

    response = client.post(
        "/adjustments",
        json=[
            {"sku": "AAA-1", "delta": 1, "reason": "delivery"},
            {"sku": "NOPE-404", "delta": 1, "reason": "delivery"},
        ],
        headers=AUTH,
    )

    assert response.status_code == 404
    assert "NOPE-404" in response.json()["detail"]
    assert quantity(client, "AAA-1") == 5


def test_going_below_zero_is_409_names_it_and_changes_nothing(client: TestClient) -> None:
    add_item(client, "AAA-1", 5)
    add_item(client, "BBB-1", 2)

    response = client.post(
        "/adjustments",
        json=[
            {"sku": "AAA-1", "delta": 1, "reason": "delivery"},
            {"sku": "BBB-1", "delta": -3, "reason": "order"},
        ],
        headers=AUTH,
    )

    assert response.status_code == 409
    assert "BBB-1" in response.json()["detail"]
    assert quantity(client, "AAA-1") == 5
    assert quantity(client, "BBB-1") == 2


def test_repeated_sku_uses_the_running_total(client: TestClient) -> None:
    add_item(client, "AAA-1", 5)

    ok = client.post(
        "/adjustments",
        json=[
            {"sku": "AAA-1", "delta": -5, "reason": "order"},
            {"sku": "AAA-1", "delta": 2, "reason": "return"},
            {"sku": "AAA-1", "delta": -2, "reason": "order"},
        ],
        headers=AUTH,
    )
    assert ok.status_code == 200
    assert [(i["sku"], i["quantity"]) for i in ok.json()] == [("AAA-1", 0)]

    refused = client.post(
        "/adjustments",
        json=[
            {"sku": "AAA-1", "delta": 3, "reason": "delivery"},
            {"sku": "AAA-1", "delta": -2, "reason": "order"},
            {"sku": "AAA-1", "delta": -2, "reason": "order"},
        ],
        headers=AUTH,
    )
    assert refused.status_code == 409
    assert quantity(client, "AAA-1") == 0


def test_needs_the_api_key(client: TestClient) -> None:
    add_item(client, "AAA-1", 5)
    body = [{"sku": "AAA-1", "delta": 1, "reason": "delivery"}]

    assert client.post("/adjustments", json=body).status_code == 401
    assert client.post("/adjustments", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
    assert quantity(client, "AAA-1") == 5


def test_rejects_an_empty_list_and_a_missing_reason(client: TestClient) -> None:
    add_item(client, "AAA-1", 5)

    assert client.post("/adjustments", json=[], headers=AUTH).status_code == 422
    missing_reason = [{"sku": "AAA-1", "delta": 1}]
    assert client.post("/adjustments", json=missing_reason, headers=AUTH).status_code == 422
