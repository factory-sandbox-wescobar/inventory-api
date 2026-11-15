from __future__ import annotations

import threading

import pytest

from inventory.store import DuplicateSku, InsufficientStock, InventoryStore, Item, NotFound


def make_item(sku: str = "WID-001", quantity: int = 10) -> Item:
    return Item(
        sku=sku,
        name="Widget",
        category="parts",
        quantity=quantity,
        reorder_level=0,
        unit_price_pence=100,
    )


def test_create_then_get() -> None:
    store = InventoryStore()
    store.create(make_item())

    assert store.get("WID-001") == make_item()


def test_create_refuses_a_duplicate_sku() -> None:
    store = InventoryStore()
    store.create(make_item())

    with pytest.raises(DuplicateSku):
        store.create(make_item())


def test_adjust_refuses_to_go_below_zero() -> None:
    store = InventoryStore()
    store.create(make_item(quantity=2))

    with pytest.raises(InsufficientStock):
        store.adjust("WID-001", -3)
    assert store.get("WID-001").quantity == 2


def test_missing_items_raise_not_found() -> None:
    store = InventoryStore()

    for call in (
        lambda: store.get("NOPE"),
        lambda: store.update("NOPE", name="x"),
        lambda: store.delete("NOPE"),
        lambda: store.adjust("NOPE", 1),
        lambda: store.adjust_many([("NOPE", 1)]),
    ):
        with pytest.raises(NotFound):
            call()


def test_adjust_many_is_all_or_nothing() -> None:
    store = InventoryStore()
    store.create(make_item("AAA-1", quantity=5))
    store.create(make_item("BBB-1", quantity=1))

    with pytest.raises(InsufficientStock) as refused:
        store.adjust_many([("AAA-1", 2), ("BBB-1", -2)])
    assert refused.value.args[0] == "BBB-1"
    with pytest.raises(NotFound) as missing:
        store.adjust_many([("AAA-1", 2), ("NOPE", 1)])
    assert missing.value.args[0] == "NOPE"

    assert store.get("AAA-1").quantity == 5
    assert store.get("BBB-1").quantity == 1


def test_adjust_many_uses_the_running_total_for_a_repeated_sku() -> None:
    store = InventoryStore()
    store.create(make_item(quantity=5))

    items = store.adjust_many([("WID-001", -5), ("WID-001", 3), ("WID-001", -3)])

    assert [item.quantity for item in items] == [0]
    assert store.get("WID-001").quantity == 0


def test_concurrent_batches_never_take_stock_below_zero() -> None:
    store = InventoryStore()
    store.create(make_item("AAA-1", quantity=10))
    store.create(make_item("BBB-1", quantity=10))
    results: list[str] = []

    def worker() -> None:
        try:
            store.adjust_many([("AAA-1", -1), ("BBB-1", -1)])
            results.append("ok")
        except InsufficientStock:
            results.append("refused")

    threads = [threading.Thread(target=worker) for _ in range(30)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count("ok") == 10
    assert store.get("AAA-1").quantity == 0
    assert store.get("BBB-1").quantity == 0
