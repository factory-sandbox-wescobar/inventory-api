from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from inventory.store import InventoryStore, Item, VersionMismatch
from tests.support import AUTH


def test_get_returns_the_version_as_an_etag(client: TestClient, widget: dict) -> None:
    assert client.get("/items/WID-001").headers["ETag"] == '"1"'


def test_patch_and_adjust_each_bump_the_version(client: TestClient, widget: dict) -> None:
    client.patch("/items/WID-001", json={"name": "New"}, headers=AUTH)
    assert client.get("/items/WID-001").headers["ETag"] == '"2"'

    client.post("/items/WID-001/adjust", json={"delta": 1, "reason": "x"}, headers=AUTH)
    assert client.get("/items/WID-001").headers["ETag"] == '"3"'


def test_patch_with_matching_if_match_succeeds(client: TestClient, widget: dict) -> None:
    response = client.patch(
        "/items/WID-001", json={"name": "New"}, headers={**AUTH, "If-Match": '"1"'}
    )

    assert response.status_code == 200
    assert response.headers["ETag"] == '"2"'


def test_patch_with_stale_if_match_is_refused_and_changes_nothing(
    client: TestClient, widget: dict
) -> None:
    response = client.patch(
        "/items/WID-001", json={"name": "New"}, headers={**AUTH, "If-Match": '"7"'}
    )

    assert response.status_code == 412
    assert client.get("/items/WID-001").json() == widget
    assert client.get("/items/WID-001").headers["ETag"] == '"1"'


def test_adjust_with_stale_if_match_is_refused_and_changes_nothing(
    client: TestClient, widget: dict
) -> None:
    response = client.post(
        "/items/WID-001/adjust",
        json={"delta": 5, "reason": "x"},
        headers={**AUTH, "If-Match": '"7"'},
    )

    assert response.status_code == 412
    assert client.get("/items/WID-001").json()["quantity"] == widget["quantity"]


def test_adjust_with_matching_if_match_succeeds(client: TestClient, widget: dict) -> None:
    response = client.post(
        "/items/WID-001/adjust",
        json={"delta": 5, "reason": "x"},
        headers={**AUTH, "If-Match": '"1"'},
    )

    assert response.status_code == 200
    assert response.json()["quantity"] == widget["quantity"] + 5


def test_a_second_writer_with_the_old_version_is_refused(
    client: TestClient, widget: dict
) -> None:
    headers = {**AUTH, "If-Match": '"1"'}
    first = client.patch("/items/WID-001", json={"name": "A"}, headers=headers)
    second = client.patch("/items/WID-001", json={"name": "B"}, headers=headers)

    assert (first.status_code, second.status_code) == (200, 412)
    assert client.get("/items/WID-001").json()["name"] == "A"


def test_a_garbled_if_match_is_refused(client: TestClient, widget: dict) -> None:
    response = client.patch(
        "/items/WID-001", json={"name": "New"}, headers={**AUTH, "If-Match": "abc"}
    )

    assert response.status_code == 412


def test_store_checks_the_version_and_changes_together() -> None:
    store = InventoryStore()
    store.create(Item("WID-001", "Widget", "parts", 10, 0, 100))

    with pytest.raises(VersionMismatch):
        store.update("WID-001", expected_version=2, name="x")
    with pytest.raises(VersionMismatch):
        store.adjust("WID-001", 1, expected_version=2)

    assert store.get("WID-001").version == 1
    assert store.adjust("WID-001", 1, expected_version=1).version == 2
