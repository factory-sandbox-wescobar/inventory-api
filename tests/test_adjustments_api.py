from __future__ import annotations

import threading

from fastapi.testclient import TestClient

from inventory.app import create_app
from inventory.store import InventoryStore, Item
from tests.support import API_KEY, AUTH


def add_item(client: TestClient, sku: str, quantity: int) -> None:
    response = client.post(
        "/items",
        json={"sku": sku, "name": sku, "quantity": quantity, "unit_price_pence": 1},
        headers=AUTH,
    )
    assert response.status_code == 201


def quantity(client: TestClient, sku: str) -> int:
    return client.get(f"/items/{sku}").json()["quantity"]


def test_applies_every_adjustment_and_returns_updated_items(
    client: TestClient, widget: dict
) -> None:
    add_item(client, "BOLT-10", 4)

    response = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -3, "reason": "order"},
            {"sku": "BOLT-10", "delta": 6, "reason": "delivery"},
        ],
        headers=AUTH,
    )

    assert response.status_code == 200
    assert [(i["sku"], i["quantity"]) for i in response.json()] == [
        ("WID-001", 7),
        ("BOLT-10", 10),
    ]
    assert quantity(client, "WID-001") == 7
    assert quantity(client, "BOLT-10") == 10


def test_unknown_sku_is_404_names_it_and_changes_nothing(
    client: TestClient, widget: dict
) -> None:
    response = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -1, "reason": "order"},
            {"sku": "NOPE-404", "delta": 1, "reason": "delivery"},
        ],
        headers=AUTH,
    )

    assert response.status_code == 404
    assert "NOPE-404" in response.json()["detail"]
    assert quantity(client, "WID-001") == 10


def test_going_below_zero_is_409_names_the_sku_and_changes_nothing(
    client: TestClient, widget: dict
) -> None:
    add_item(client, "BOLT-10", 5)

    response = client.post(
        "/adjustments",
        json=[
            {"sku": "BOLT-10", "delta": -1, "reason": "order"},
            {"sku": "WID-001", "delta": -11, "reason": "order"},
        ],
        headers=AUTH,
    )

    assert response.status_code == 409
    assert "WID-001" in response.json()["detail"]
    assert quantity(client, "WID-001") == 10
    assert quantity(client, "BOLT-10") == 5


def test_repeated_sku_uses_the_running_total(client: TestClient, widget: dict) -> None:
    refused = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -6, "reason": "order"},
            {"sku": "WID-001", "delta": -6, "reason": "order"},
        ],
        headers=AUTH,
    )
    assert refused.status_code == 409
    assert quantity(client, "WID-001") == 10

    allowed = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -10, "reason": "order"},
            {"sku": "WID-001", "delta": 4, "reason": "delivery"},
        ],
        headers=AUTH,
    )
    assert allowed.status_code == 200
    assert [i["quantity"] for i in allowed.json()] == [4]
    assert quantity(client, "WID-001") == 4


def test_needs_the_api_key(client: TestClient, widget: dict) -> None:
    body = [{"sku": "WID-001", "delta": -1, "reason": "order"}]

    assert client.post("/adjustments", json=body).status_code == 401
    assert quantity(client, "WID-001") == 10


def test_concurrent_batches_never_oversell() -> None:
    store = InventoryStore()
    store.create(
        Item(
            sku="WID-001",
            name="Widget",
            category="parts",
            quantity=10,
            reorder_level=0,
            unit_price_pence=1,
        )
    )
    client = TestClient(create_app(api_key=API_KEY, store=store))
    statuses: list[int] = []

    def remove_one_pair() -> None:
        body = [
            {"sku": "WID-001", "delta": -1, "reason": "order"},
            {"sku": "WID-001", "delta": -1, "reason": "order"},
        ]
        statuses.append(client.post("/adjustments", json=body, headers=AUTH).status_code)

    threads = [threading.Thread(target=remove_one_pair) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(statuses) == [200] * 5 + [409] * 5
    assert store.get("WID-001").quantity == 0
